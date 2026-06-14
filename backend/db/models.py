import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    JSON,
    Integer,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from db.session import Base
import enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SessionStatus(str, enum.Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


class WorkflowNodeStatus(str, enum.Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


class MessageRole(str, enum.Enum):
    USER      = "user"
    ASSISTANT = "assistant"


# ---------------------------------------------------------------------------
# ResearchSession
# ---------------------------------------------------------------------------

class ResearchSession(Base):
    """
    One session = one company research job.
    Created by the user, holds the final report once workflow completes.
    """
    __tablename__ = "research_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_name: Mapped[str]   = mapped_column(String(255), nullable=False)
    website:      Mapped[str]   = mapped_column(String(500), nullable=False)
    objective:    Mapped[str]   = mapped_column(Text, nullable=False)

    status: Mapped[SessionStatus] = mapped_column(
        SAEnum(SessionStatus),
        default=SessionStatus.PENDING,
        nullable=False,
    )

    # Structured briefing — populated after workflow completes
    report: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Raw scraped + searched content — useful for debugging / re-runs
    raw_research: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active:     Mapped[bool]           = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────
    workflow_runs: Mapped[list["WorkflowRun"]]   = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatMessage"]]   = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ResearchSession id={self.id} company={self.company_name} status={self.status}>"


# ---------------------------------------------------------------------------
# WorkflowRun
# ---------------------------------------------------------------------------

class WorkflowRun(Base):
    """
    Tracks a single execution of the LangGraph workflow.
    One session can have multiple runs (e.g. re-runs after failure).
    """
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[WorkflowNodeStatus] = mapped_column(
        SAEnum(WorkflowNodeStatus),
        default=WorkflowNodeStatus.PENDING,
        nullable=False,
    )

    # LangGraph node progress — e.g. {"scrape": "completed", "research": "running"}
    node_statuses: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Full LangGraph state snapshot — useful for resuming / debugging
    graph_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at:   Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active:    Mapped[bool]               = mapped_column(Boolean, default=True, nullable=False)
    created_at:   Mapped[datetime]           = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────
    session: Mapped["ResearchSession"] = relationship(back_populates="workflow_runs")

    def __repr__(self) -> str:
        return f"<WorkflowRun id={self.id} session={self.session_id} status={self.status}>"


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------

class ChatMessage(Base):
    """
    Follow-up chat messages tied to a session.
    The report acts as context for all assistant replies.
    """
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    role:    Mapped[MessageRole] = mapped_column(SAEnum(MessageRole), nullable=False)
    content: Mapped[str]        = mapped_column(Text, nullable=False)

    # Token usage — useful for cost tracking
    prompt_tokens:     Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    is_active:  Mapped[bool]     = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────
    session: Mapped["ResearchSession"] = relationship(back_populates="chat_messages")

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} role={self.role} session={self.session_id}>"


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Correlation / tracing
    request_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    workflow_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Error classification
    error_type: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Request context
    path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    method: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Structured debugging info
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )