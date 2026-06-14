import uuid
from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel

from db.models import WorkflowNodeStatus
from config.constants import ALL_WORKFLOW_NODES


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class RunWorkflowRequest(BaseModel):
    """Optional overrides when triggering a workflow run."""
    force_rerun: bool = False   # Re-run even if session already has a report

    model_config = {
        "json_schema_extra": {
            "example": {"force_rerun": False}
        }
    }


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class WorkflowRunResponse(BaseModel):
    id:            uuid.UUID
    session_id:    uuid.UUID
    status:        WorkflowNodeStatus
    node_statuses: Optional[Dict[str, str]] = None
    error_message: Optional[str]   = None
    started_at:    Optional[datetime] = None
    completed_at:  Optional[datetime] = None
    created_at:    datetime

    model_config = {"from_attributes": True}


class WorkflowStatusResponse(BaseModel):
    """
    Returned by GET /workflows/status/{id}.
    Combines session status with latest run node-level progress.
    """
    session_id:          uuid.UUID
    status:              WorkflowNodeStatus
    node_statuses:       Dict[str, str] = {}   # dynamic: node_name → "pending|running|completed|failed"
    last_completed_node: Optional[str]  = None
    error_message:       Optional[str]  = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "running",
                "node_statuses": {
                    "planner": "completed",
                    "competitor_research": "completed",
                    "web_research": "running",
                    "summarize_content": "pending",
                    "structured_insights": "pending",
                    "analyze": "pending",
                    "quality_check": "pending",
                    "generate_report": "pending",
                },
                "last_completed_node": "competitor_research",
            }
        }
    }


class WorkflowStartedResponse(BaseModel):
    """Returned immediately when a workflow run is triggered."""
    run_id:     uuid.UUID
    session_id: uuid.UUID
    message:    str = "Workflow started"


class WorkflowResumeResponse(BaseModel):
    """Returned when a failed workflow is resumed from checkpoint."""
    run_id:              uuid.UUID
    session_id:          uuid.UUID
    resumed_from_node:   str
    message:             str = "Workflow resumed from checkpoint"