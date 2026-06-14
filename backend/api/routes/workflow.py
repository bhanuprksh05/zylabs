"""
api/routes/workflow.py
-----------------------
Workflow endpoints:
  POST /run/{id}     — Start the LangGraph research workflow
  POST /resume/{id}  — Resume a failed workflow from its last checkpoint
  GET  /status/{id}  — Poll node-level progress

The real LangGraph workflow runs in a FastAPI BackgroundTask.
It streams node completion events and updates the DB in real-time.
"""
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from api.schemas import (
    RunWorkflowRequest,
    WorkflowStatusResponse,
    WorkflowStartedResponse,
    WorkflowResumeResponse,
)
from db.models import SessionStatus, WorkflowNodeStatus
from db.session import AsyncSessionLocal
from db.repository import (
    SessionRepository,
    WorkflowRunRepository,
    get_session_repo,
    get_workflow_repo,
)
from config.constants import ALL_WORKFLOW_NODES

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background task — runs the real LangGraph graph
# ---------------------------------------------------------------------------

async def run_langgraph_workflow(session_id: uuid.UUID, run_id: uuid.UUID) -> None:
    """
    Background task that executes the full LangGraph research workflow.

    Responsibilities:
      1. Mark the run as RUNNING.
      2. Build the initial ResearchState from session data.
      3. Check for a resume checkpoint and merge it if present.
      4. Stream through the graph (astream, stream_mode="updates").
      5. After each node event → update node_statuses + save checkpoint.
      6. On completion → save the report and mark COMPLETED.
      7. On unhandled error → mark FAILED (with error preserved in graph_state).
    """
    # Import the compiled graph here so startup errors surface clearly
    from core.graph.workflow import research_graph
    from core.graph.state import ResearchState

    async with AsyncSessionLocal() as db:
        session_repo = SessionRepository(db)
        workflow_repo = WorkflowRunRepository(db)

        try:
            # ── 1. Mark run as started ────────────────────────────────────
            await workflow_repo.mark_started(run_id)

            # ── 2. Fetch session data ─────────────────────────────────────
            session = await session_repo.get_by_id(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found in DB")

            # ── 3. Build initial state ────────────────────────────────────
            initial_state: ResearchState = {
                "company_name":       session.company_name,
                "website":            session.website,
                "objective":          session.objective,
                "session_id":         str(session_id),
                "run_id":             str(run_id),
                "research_plan":      {},
                "raw_search_results": [],
                "scraped_content":    "",
                "competitor_data":    {},
                "content_summary":    "",
                "structured_data":    {},
                "analysis":           {},
                "quality_score":      0.0,
                "quality_issues":     [],
                "retry_count":        0,
                "report":             {},
                "last_completed_node": "",
                "error_count":        0,
                "errors":             [],
            }

            # ── Resume from checkpoint if available ───────────────────────
            current_run = await workflow_repo.get_by_id(run_id)
            if current_run and current_run.graph_state:
                resume = current_run.graph_state.get("resume_state")
                if resume:
                    initial_state.update(resume)
                    logger.info(
                        f"Resuming from checkpoint: "
                        f"last_node={resume.get('last_completed_node')}"
                    )

            # Accumulate the full state as the graph streams partial updates
            final_state: dict = dict(initial_state)

            # ── 4. Stream through the LangGraph ──────────────────────────
            async for event in research_graph.astream(
                initial_state,
                stream_mode="updates",
            ):
                for node_name, state_delta in event.items():
                    if node_name == "__end__":
                        continue

                    logger.info(f"Node completed: {node_name}")

                    # Merge partial update into accumulated state
                    final_state.update(state_delta)

                    # Persist node completion to DB
                    await workflow_repo.update_node_status(
                        run_id, node_name, "completed"
                    )

                    # Save checkpoint for recoverability
                    await workflow_repo.save_checkpoint(
                        run_id=run_id,
                        last_node=node_name,
                        state_snapshot=_safe_serialize(final_state),
                    )

            # ── 5. Persist final report ───────────────────────────────────
            report = final_state.get("report", {})
            raw_research = {
                "search_results_count": len(final_state.get("raw_search_results", [])),
                "scraped_chars":        len(final_state.get("scraped_content", "")),
                "competitor_data":      final_state.get("competitor_data", {}),
                "content_summary":      final_state.get("content_summary", ""),
                "quality_score":        final_state.get("quality_score", 0),
                "retry_count":          final_state.get("retry_count", 0),
                "errors":               final_state.get("errors", []),
            }

            await session_repo.save_report(
                session_id,
                report=report,
                raw_research=raw_research,
            )

            await workflow_repo.mark_completed(
                run_id,
                graph_state=_safe_serialize(final_state),
            )
            logger.info(f"Workflow completed for session {session_id}")

        except Exception as exc:
            logger.error(
                f"Workflow {run_id} failed: {exc}",
                exc_info=True,
            )
            await workflow_repo.mark_failed(run_id, error_message=str(exc))
            await session_repo.update_status(
                session_id,
                status=SessionStatus.FAILED,
                error_message=str(exc),
            )


def _safe_serialize(state: dict) -> dict:
    """Return a JSON-serialisable copy of the state, coercing unserializable values."""
    import json
    safe: dict = {}
    for key, value in state.items():
        try:
            json.dumps(value)
            safe[key] = value
        except (TypeError, ValueError):
            safe[key] = str(value)
    return safe


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/run/{id}", response_model=WorkflowStartedResponse)
async def run_workflow(
    id: uuid.UUID,
    payload: RunWorkflowRequest,
    background_tasks: BackgroundTasks,
    session_repo: SessionRepository = Depends(get_session_repo),
    workflow_repo: WorkflowRunRepository = Depends(get_workflow_repo),
):
    """
    Start the LangGraph research workflow for a session.
    The workflow runs in the background; poll /status/{id} for progress.
    """
    session = await session_repo.get_by_id(id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found with id: {id}",
        )

    # Prevent concurrent or redundant runs
    latest_run = await workflow_repo.get_latest_for_session(id)
    if latest_run and latest_run.status in (
        WorkflowNodeStatus.PENDING,
        WorkflowNodeStatus.RUNNING,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is already running or pending for this session.",
        )

    if session.status == SessionStatus.COMPLETED and not payload.force_rerun:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Workflow already completed successfully. "
                "Use force_rerun=True to run again."
            ),
        )

    # Update session status and create a new run record
    await session_repo.update_status(id, status=SessionStatus.RUNNING)
    run = await workflow_repo.create(id)

    # Launch real LangGraph workflow in background
    background_tasks.add_task(run_langgraph_workflow, id, run.id)

    return WorkflowStartedResponse(
        run_id=run.id,
        session_id=id,
        message=(
            "Research workflow started. "
            "Poll GET /api/v1/workflows/status/{id} for real-time progress."
        ),
    )


@router.post("/resume/{id}", response_model=WorkflowResumeResponse)
async def resume_workflow(
    id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session_repo: SessionRepository = Depends(get_session_repo),
    workflow_repo: WorkflowRunRepository = Depends(get_workflow_repo),
):
    """
    Resume a failed workflow from its last saved checkpoint.

    Requirements:
      - The latest run for this session must have status=FAILED.
      - The failed run must have a graph_state checkpoint saved.

    The new run will inherit the failed run's state and skip already-completed nodes.
    """
    session = await session_repo.get_by_id(id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found with id: {id}",
        )

    latest_run = await workflow_repo.get_latest_for_session(id)
    if not latest_run or latest_run.status != WorkflowNodeStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No failed workflow run found. Use POST /run/{id} to start fresh.",
        )

    checkpoint = latest_run.graph_state or {}
    last_node = checkpoint.get("last_completed_node", "")

    if not last_node:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No checkpoint found in failed run. "
                "Use POST /run/{id} to start a fresh run."
            ),
        )

    # Create a new run and seed it with the checkpoint state
    await session_repo.update_status(id, status=SessionStatus.RUNNING)
    new_run = await workflow_repo.create(id)

    # Copy checkpoint into the new run so the background task can resume
    resume_state = checkpoint.get("resume_state", checkpoint)
    await workflow_repo.save_checkpoint(
        run_id=new_run.id,
        last_node=last_node,
        state_snapshot=resume_state,
    )

    background_tasks.add_task(run_langgraph_workflow, id, new_run.id)

    return WorkflowResumeResponse(
        run_id=new_run.id,
        session_id=id,
        resumed_from_node=last_node,
        message=f"Workflow resumed from checkpoint after node: {last_node}",
    )


@router.get("/status/{id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    id: uuid.UUID,
    session_repo: SessionRepository = Depends(get_session_repo),
    workflow_repo: WorkflowRunRepository = Depends(get_workflow_repo),
):
    """
    Poll the real-time status of the latest workflow run for a session.
    Returns node-level progress for all 8 workflow nodes.
    """
    session = await session_repo.get_by_id(id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found with id: {id}",
        )

    run = await workflow_repo.get_latest_for_session(id)
    if not run:
        return WorkflowStatusResponse(
            session_id=id,
            status=WorkflowNodeStatus.PENDING,
            node_statuses={node: "pending" for node in ALL_WORKFLOW_NODES},
        )

    node_statuses = run.node_statuses or {
        node: "pending" for node in ALL_WORKFLOW_NODES
    }
    last_node: Optional[str] = None
    if run.graph_state:
        last_node = run.graph_state.get("last_completed_node")

    return WorkflowStatusResponse(
        session_id=id,
        status=run.status,
        node_statuses=node_statuses,
        last_completed_node=last_node,
        error_message=run.error_message,
    )
