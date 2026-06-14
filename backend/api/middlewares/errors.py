import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            f"HTTP exception: {exc.detail} - Status: {exc.status_code}",
            extra={"request_id": request_id, "status_code": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=str(exc.detail),
                code=f"HTTP_{exc.status_code}",
            ).model_dump(exclude_none=True),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        # Formulate a clean error description
        errors = exc.errors()
        details = "; ".join(
            [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in errors]
        )
        logger.warning(
            f"Validation error: {details}",
            extra={"request_id": request_id},
        )
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="Validation Error",
                detail=details,
                code="VALIDATION_ERROR",
            ).model_dump(exclude_none=True),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "Unhandled exception occurred",
            exc_info=exc,
            extra={"request_id": request_id},
        )
        
        # Include detailed error trace only in non-production/debug mode
        detail = str(exc) if app.debug else "An unexpected error occurred"
        
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal Server Error",
                detail=detail,
                code="INTERNAL_SERVER_ERROR",
            ).model_dump(exclude_none=True),
        )
