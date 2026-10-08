"""FastAPI entry point: wires config, the LLM provider and storage into the API."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_error_handlers
from app.api.routes import router
from app.config import Settings, get_settings
from app.llm.factory import build_provider
from app.llm.interface import LLMProvider
from app.services.session_store import InMemorySessionRepository, SessionRepository
from app.services.sessions import SessionService


def create_app(
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
    repository: SessionRepository | None = None,
) -> FastAPI:
    """Build the app. Tests pass their own settings, provider and repository."""
    settings = settings or get_settings()
    app = FastAPI(title="Document Intake Assistant", version="0.1.0")
    app.state.settings = settings
    app.state.service = SessionService(
        repository=repository or InMemorySessionRepository(),
        provider=provider or build_provider(settings),
    )
    register_error_handlers(app)
    app.include_router(router)

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = create_app()
