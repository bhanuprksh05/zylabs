import uuid
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import ResearchSession, SessionStatus

logger = logging.getLogger(__name__)


class SessionRepository:
    """All DB operations for ResearchSession."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        company_name: str,
        website: str,
        objective: str,
    ) -> ResearchSession:
        session = ResearchSession(
            company_name=company_name,
            website=website,
            objective=objective,
            status=SessionStatus.PENDING,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        logger.info("Session created", extra={"session_id": str(session.id)})
        return session

    async def get_by_id(
        self,
        session_id: uuid.UUID,
        load_relations: bool = False,
    ) -> Optional[ResearchSession]:
        stmt = select(ResearchSession).where(
            ResearchSession.id == session_id,
            ResearchSession.is_active == True,
        )

        if load_relations:
            stmt = stmt.options(
                selectinload(ResearchSession.workflow_runs),
                selectinload(ResearchSession.chat_messages),
            )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ResearchSession]:
        stmt = (
            select(ResearchSession)
            .where(ResearchSession.is_active == True)
            .order_by(desc(ResearchSession.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        session_id: uuid.UUID,
        status: SessionStatus,
        error_message: Optional[str] = None,
    ) -> Optional[ResearchSession]:
        session = await self.get_by_id(session_id)
        if not session:
            return None

        session.status = status
        session.updated_at = datetime.utcnow()
        if error_message:
            session.error_message = error_message

        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def save_report(
        self,
        session_id: uuid.UUID,
        report: dict,
        raw_research: Optional[dict] = None,
    ) -> Optional[ResearchSession]:
        session = await self.get_by_id(session_id)
        if not session:
            return None

        session.report = report
        session.status = SessionStatus.COMPLETED
        session.updated_at = datetime.utcnow()
        if raw_research:
            session.raw_research = raw_research

        await self.db.commit()
        await self.db.refresh(session)
        logger.info("Report saved", extra={"session_id": str(session_id)})
        return session

    async def delete(self, session_id: uuid.UUID) -> bool:
        session = await self.get_by_id(session_id)
        if not session:
            return False

        session.is_active = False
        await self.db.commit()
        logger.info("Session soft deleted", extra={"session_id": str(session_id)})
        return True