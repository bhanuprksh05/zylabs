from typing import Any, Optional
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error shape returned by exception handlers."""
    error:   str
    detail:  Optional[str] = None
    code:    Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "error":  "Session not found",
                "detail": "No session exists with id: abc-123",
                "code":   "SESSION_NOT_FOUND",
            }
        }
    }


class SuccessResponse(BaseModel):
    """Generic success acknowledgement."""
    message: str
    data:    Optional[Any] = None


class PaginationParams(BaseModel):
    """Reusable query param model for paginated list endpoints."""
    limit:  int = 20
    offset: int = 0