import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — runs on startup and shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("Starting Research Copilot API", extra={"env": settings.env})

    # DB
    from db.session import init_db
    await init_db()
    logger.info("Database connected")

    # Redis
    from services.redis import init_redis, close_redis
    await init_redis()
    logger.info("Redis connected")

    yield  # app is running

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("Shutting down Research Copilot API")
    await close_redis()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="Research Copilot API",
        description="AI-powered company research and meeting preparation",
        version="1.0.0",
        docs_url="/docs" if settings.env != "production" else None,
        redoc_url="/redoc" if settings.env != "production" else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.middlewares.logging import LoggingMiddleware
    from api.middlewares.errors import register_exception_handlers

    app.add_middleware(LoggingMiddleware)
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────
    from api.routes.sessions import router as sessions_router
    from api.routes.workflow import router as workflow_router
    from api.routes.chat import router as chat_router

    app.include_router(sessions_router, prefix="/api/v1/sessions", tags=["Sessions"])
    app.include_router(workflow_router, prefix="/api/v1/workflows", tags=["Workflow"])
    app.include_router(chat_router,     prefix="/api/v1/chat",      tags=["Chat"])

    # ── Health check ──────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok", "env": settings.env}

    return app


app = create_app()


# ---------------------------------------------------------------------------
# Dev entry point — run with: python main.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.env == "development",
        log_level=settings.log_level.lower(),
    )