from db.repository.session  import SessionRepository
from db.repository.workflow import WorkflowRunRepository
from db.repository.chat     import ChatRepository
from db.repository.error import ErrorLogRepository

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db


# ---------------------------------------------------------------------------
# Dependency helpers — inject directly into route params via Depends()
# ---------------------------------------------------------------------------

async def get_session_repo(
    db: AsyncSession = Depends(get_db),
) -> SessionRepository:
    return SessionRepository(db)


async def get_workflow_repo(
    db: AsyncSession = Depends(get_db),
) -> WorkflowRunRepository:
    return WorkflowRunRepository(db)


async def get_chat_repo(
    db: AsyncSession = Depends(get_db),
) -> ChatRepository:
    return ChatRepository(db)


__all__ = [
    "SessionRepository",
    "WorkflowRunRepository",
    "ChatRepository",
    "ErrorLogRepository",
    "get_session_repo",
    "get_workflow_repo",
    "get_chat_repo",
    "get_error_log_repo",
]
