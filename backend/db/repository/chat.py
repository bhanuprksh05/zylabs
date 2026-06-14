import uuid
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ChatMessage, MessageRole

logger = logging.getLogger(__name__)


class ChatRepository:
    """All DB operations for ChatMessage."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: MessageRole,
        content: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_history(
        self,
        session_id: uuid.UUID,
        limit: int = 50,
    ) -> list[ChatMessage]:
        """
        Returns messages oldest-first — correct order
        for passing to the LLM as conversation history.
        """
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.is_active == True,
            )
            .order_by(ChatMessage.created_at)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_history_as_dicts(
        self,
        session_id: uuid.UUID,
        limit: int = 50,
    ) -> list[dict]:
        """
        Returns history formatted for LangChain:
        [{"role": "user", "content": "..."}, ...]
        """
        messages = await self.get_history(session_id, limit)
        return [{"role": m.role.value, "content": m.content} for m in messages]

    async def clear_history(self, session_id: uuid.UUID) -> int:
        """Soft deletes all messages for a session. Returns count deactivated."""
        stmt = select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.is_active == True,
        )
        result = await self.db.execute(stmt)
        messages = result.scalars().all()
        count = len(messages)

        for msg in messages:
            msg.is_active = False

        await self.db.commit()
        logger.info(
            "Chat history soft cleared",
            extra={"session_id": str(session_id), "count": count},
        )
        return count