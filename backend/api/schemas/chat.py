import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator

from db.models import MessageRole


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message cannot be blank")
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "What is their main product and who are their competitors?"
            }
        }
    }


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class ChatMessageResponse(BaseModel):
    id:         uuid.UUID
    session_id: uuid.UUID
    role:       MessageRole
    content:    str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    """Returned after each chat turn — includes both user msg and assistant reply."""
    user_message:      ChatMessageResponse
    assistant_message: ChatMessageResponse


class ChatHistoryResponse(BaseModel):
    session_id: uuid.UUID
    messages:   list[ChatMessageResponse]
    total:      int


class TokenUsage(BaseModel):
    """Optional token tracking in responses."""
    prompt_tokens:     Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens:      Optional[int] = None