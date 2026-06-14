import uuid
import time
import logging
import traceback

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from db.session import async_session_maker  # ✅ use your async sessionmaker
from db.repository.error import ErrorLogRepository

logger = logging.getLogger("api.request")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate or retrieve a request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start_time = time.time()

        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )

        try:
            response = await call_next(request)

        except Exception as e:
            duration = time.time() - start_time

            logger.error(
                f"Request failed: {request.method} {request.url.path} - Exception: {str(e)} - Duration: {duration:.3f}s",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration": duration,
                },
                exc_info=True,
            )
            try:
                async with async_session_maker() as db:
                    repo = ErrorLogRepository(db)

                    await repo.create_error(
                        error_type=type(e).__name__,
                        message=str(e),
                        request_id=request_id,
                        status_code=500,
                        path=str(request.url),
                        method=request.method,
                        stack_trace=traceback.format_exc(),
                    )
            except Exception:
                # Prevent cascading failure if DB logging fails
                logger.exception("Failed to write error log to DB")

            raise e  # re-raise for FastAPI handlers

        duration = time.time() - start_time
        response.headers["X-Request-ID"] = request_id

        logger.info(
            f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} - Duration: {duration:.3f}s",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": duration,
            },
        )

        return response