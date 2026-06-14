import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator

from db.models import SessionStatus


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    company_name: str
    website:      str
    objective:    str

    @field_validator("company_name")
    @classmethod
    def company_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("company_name cannot be blank")
        return v.strip()

    @field_validator("objective")
    @classmethod
    def objective_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("objective cannot be blank")
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "example": {
                "company_name": "Anthropic",
                "website":      "https://anthropic.com",
                "objective":    "Preparing for a sales meeting with their procurement team",
            }
        }
    }


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class SessionResponse(BaseModel):
    id:           uuid.UUID
    company_name: str
    website:      str
    objective:    str
    status:       SessionStatus
    created_at:   datetime
    updated_at:   datetime

    model_config = {"from_attributes": True}


class SessionDetailResponse(SessionResponse):
    """Full session including report — returned after workflow completes."""
    report:        Optional[dict] = None
    error_message: Optional[str] = None


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    total: int
    limit: int
    offset: int