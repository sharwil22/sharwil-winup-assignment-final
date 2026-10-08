"""HTTP routes. Thin: parse the request, call `SessionService`, shape the response."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import PlainTextResponse

from app.api.errors import ApiError
from app.api.schemas import (
    ErrorEnvelope,
    HealthResponse,
    PatchField,
    PostMessage,
    SessionView,
    TurnResult,
    session_view,
    turn_result,
)
from app.config import Settings
from app.documents.generator import render
from app.domain.models import Gift
from app.services.sessions import EditRejected, SessionService

ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorEnvelope} for code in (404, 409, 422, 500, 503)
}

router = APIRouter(prefix="/api", responses=ERRORS)


def get_service(request: Request) -> SessionService:
    service: SessionService = request.app.state.service
    return service


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


Service = Annotated[SessionService, Depends(get_service)]


@router.get("/health", response_model=HealthResponse)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok", provider=settings.llm_provider, model_configured=settings.model_configured
    )


@router.post("/sessions", response_model=SessionView, status_code=status.HTTP_201_CREATED)
def create_session(service: Service) -> SessionView:
    return session_view(service.start())


@router.get("/sessions/{session_id}", response_model=SessionView)
def get_session(session_id: str, service: Service) -> SessionView:
    return session_view(service.get(session_id))


# Plain `def`: FastAPI runs it in a worker thread, so the blocking model call doesn't stall
# the event loop.
@router.post("/sessions/{session_id}/messages", response_model=TurnResult)
def post_message(session_id: str, body: PostMessage, service: Service) -> TurnResult:
    content = body.content.strip()
    if not content:
        raise ApiError(422, "validation_error", "content: message must not be blank")
    session, outcome = service.send_message(session_id, content, body.expected_version)
    return turn_result(session, outcome)


@router.patch("/sessions/{session_id}/fields", response_model=SessionView)
def edit_field(session_id: str, body: PatchField, service: Service) -> SessionView:
    value: Any = body.value
    if body.path == "specific_gifts" and isinstance(value, list):
        value = [Gift(item=g.item, recipient=g.recipient) for g in value]
    try:
        session = service.edit_field(session_id, body.path, value, body.expected_version)
    except EditRejected as exc:
        raise ApiError(422, "validation_error", f"{body.path}: {exc}") from exc
    return session_view(session)


@router.get(
    "/sessions/{session_id}/document",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/markdown": {}}}},
)
def get_document(session_id: str, service: Service) -> PlainTextResponse:
    return PlainTextResponse(
        render(service.get(session_id).state),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="personal-wishes-draft.md"'},
    )
