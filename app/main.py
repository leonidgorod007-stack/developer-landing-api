"""
Application factory & assembly.

Wires everything together: config → logging → DI container → middleware →
CORS → exception handlers → routers → static frontend. `create_app()` is the
single entry point used by both uvicorn and the tests.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import contact, health, metrics
from app.config import BASE_DIR, Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestLoggingMiddleware
from app.dependencies import build_container
from app.logging_config import setup_logging

FRONTEND_DIR = BASE_DIR / "frontend"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logger = setup_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Build long-lived singletons once, expose via app.state.
        app.state.container = build_container(settings)
        logger.info(
            "%s v%s starting (env=%s, ai=%s, email=%s)",
            settings.app_name, __version__, settings.app_env,
            "live" if settings.ai_configured else "fallback",
            "smtp" if settings.email_configured else "console",
        )
        yield
        logger.info("Shutting down.")

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Backend service for a developer landing page: validated contact "
            "form, AI triage of messages, email notifications, rate limiting, "
            "file-based logging and metrics."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Order matters: request-logging runs outermost so it times everything;
    # CORS is added after so it wraps responses (incl. preflight).
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

    register_exception_handlers(app)

    # API routes under /api.
    app.include_router(contact.router, prefix="/api")
    app.include_router(health.router, prefix="/api")
    app.include_router(metrics.router, prefix="/api")

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the landing page at / and any static assets under /assets."""
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        return

    assets = FRONTEND_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    async def landing_page() -> FileResponse:
        return FileResponse(index)


# Module-level app so `uvicorn app.main:app` works out of the box.
app = create_app()
