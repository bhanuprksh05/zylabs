import uuid
import logging
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ErrorLog

logger = logging.getLogger(__name__)


class ErrorLogRepository:
    """All DB operations for ErrorLog."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_error(
        self,
        *,
        error_type: str,
        message: str,
        request_id: Optional[str] = None,
        workflow_run_id: Optional[uuid.UUID] = None,
        status_code: Optional[int] = None,
        path: Optional[str] = None,
        method: Optional[str] = None,
        stack_trace: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> ErrorLog:
        error = ErrorLog(
            error_type=error_type,
            message=message,
            request_id=request_id,
            workflow_run_id=workflow_run_id,
            status_code=status_code,
            path=path,
            method=method,
            stack_trace=stack_trace,
            extra=extra,
        )

        self.db.add(error)
        await self.db.commit()
        await self.db.refresh(error)

        return error

    async def get_by_id(self, error_id: uuid.UUID) -> Optional[ErrorLog]:
        stmt = select(ErrorLog).where(ErrorLog.id == error_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_errors(
        self,
        *,
        limit: int = 50,
        error_type: Optional[str] = None,
        workflow_run_id: Optional[uuid.UUID] = None,
    ) -> List[ErrorLog]:
        stmt = select(ErrorLog)

        if error_type:
            stmt = stmt.where(ErrorLog.error_type == error_type)

        if workflow_run_id:
            stmt = stmt.where(ErrorLog.workflow_run_id == workflow_run_id)

        stmt = stmt.order_by(ErrorLog.created_at.desc()).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_old_errors(self, before_datetime) -> int:
        """
        Hard delete old logs (for retention policy).
        Returns number of deleted rows (approx).
        """
        stmt = select(ErrorLog).where(ErrorLog.created_at < before_datetime)
        result = await self.db.execute(stmt)
        errors = result.scalars().all()

        count = len(errors)

        for err in errors:
            await self.db.delete(err)

        await self.db.commit()

        logger.info("Old error logs deleted", extra={"count": count})

        return count