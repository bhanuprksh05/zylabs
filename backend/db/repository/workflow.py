import uuid
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import WorkflowRun, WorkflowNodeStatus
from config.constants import ALL_WORKFLOW_NODES

logger = logging.getLogger(__name__)


class WorkflowRunRepository:
    """All DB operations for WorkflowRun."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, session_id: uuid.UUID) -> WorkflowRun:
        """
        Create a new WorkflowRun with all 8 workflow nodes initialised to 'pending'.
        """
        run = WorkflowRun(
            session_id=session_id,
            status=WorkflowNodeStatus.PENDING,
            node_statuses={node: "pending" for node in ALL_WORKFLOW_NODES},
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        logger.info(
            "WorkflowRun created",
            extra={"run_id": str(run.id), "session_id": str(session_id)},
        )
        return run

    async def get_by_id(self, run_id: uuid.UUID) -> Optional[WorkflowRun]:
        stmt = select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.is_active == True,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_session(
        self,
        session_id: uuid.UUID,
    ) -> Optional[WorkflowRun]:
        stmt = (
            select(WorkflowRun)
            .where(
                WorkflowRun.session_id == session_id,
                WorkflowRun.is_active == True,
            )
            .order_by(desc(WorkflowRun.created_at))
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_started(self, run_id: uuid.UUID) -> Optional[WorkflowRun]:
        run = await self.get_by_id(run_id)
        if not run:
            return None

        run.status = WorkflowNodeStatus.RUNNING
        run.started_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def update_node_status(
        self,
        run_id: uuid.UUID,
        node_name: str,
        node_status: str,
    ) -> Optional[WorkflowRun]:
        """
        Update a single node's status inside the node_statuses JSON.
        Rebuilds the dict on reassignment — SQLAlchemy won't detect
        in-place mutation of a JSON column.
        """
        run = await self.get_by_id(run_id)
        if not run:
            return None

        updated = dict(run.node_statuses or {})
        updated[node_name] = node_status
        run.node_statuses = updated

        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def save_checkpoint(
        self,
        run_id: uuid.UUID,
        last_node: str,
        state_snapshot: dict,
    ) -> Optional[WorkflowRun]:
        """
        Persist a checkpoint after each node completes.
        Stores the full serialised state in graph_state for resume logic.

        The `state_snapshot` should already be JSON-serialisable
        (call `_serialize_state()` before passing).
        """
        run = await self.get_by_id(run_id)
        if not run:
            return None

        run.graph_state = {
            "last_completed_node": last_node,
            "resume_state": state_snapshot,
        }

        await self.db.commit()
        await self.db.refresh(run)
        logger.debug(
            "Checkpoint saved",
            extra={"run_id": str(run_id), "last_node": last_node},
        )
        return run

    async def mark_completed(
        self,
        run_id: uuid.UUID,
        graph_state: Optional[dict] = None,
    ) -> Optional[WorkflowRun]:
        run = await self.get_by_id(run_id)
        if not run:
            return None

        run.status = WorkflowNodeStatus.COMPLETED
        run.completed_at = datetime.utcnow()
        if graph_state:
            run.graph_state = graph_state

        await self.db.commit()
        await self.db.refresh(run)
        logger.info("WorkflowRun completed", extra={"run_id": str(run_id)})
        return run

    async def mark_failed(
        self,
        run_id: uuid.UUID,
        error_message: str,
        graph_state: Optional[dict] = None,
    ) -> Optional[WorkflowRun]:
        run = await self.get_by_id(run_id)
        if not run:
            return None

        run.status = WorkflowNodeStatus.FAILED
        run.completed_at = datetime.utcnow()
        run.error_message = error_message
        if graph_state:
            run.graph_state = graph_state

        await self.db.commit()
        await self.db.refresh(run)
        logger.warning(
            "WorkflowRun failed",
            extra={"run_id": str(run_id), "error": error_message},
        )
        return run