"""Request and response DTOs: the public API contract (also published as OpenAPI).

Responses always carry the full, server-computed view (state, document, progress), so the
UI never derives state on its own and can't drift from the source of truth.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.documents.generator import render
from app.domain.models import FIELD_LABELS, FIELD_PATHS, FieldPath, FieldStatus
from app.domain.planner import is_complete, next_focus, progress
from app.services.interview import TurnOutcome, planner_question
from app.services.session_store import Session

MAX_MESSAGE_LENGTH = 2000


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PostMessage(_Request):
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    expected_version: int = Field(ge=0)


class GiftIn(_Request):
    item: str
    recipient: str


class PatchField(_Request):
    path: FieldPath
    value: bool | str | list[str] | list[GiftIn]
    expected_version: int = Field(ge=0)


class FieldView(BaseModel):
    path: FieldPath
    label: str
    value: Any
    status: FieldStatus
    candidate: Any
    note: str | None
    # Provenance: where the confirmed value came from.
    source: Literal["chat", "edit"] | None
    source_turn: int | None  # 1-based user message number
    evidence: str | None  # the user's own words
    previous_value: Any  # what a correction replaced


class MessageView(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChangeView(BaseModel):
    path: FieldPath
    label: str
    old_value: Any
    new_value: Any
    old_status: FieldStatus
    new_status: FieldStatus


class RejectedUpdateView(BaseModel):
    path: FieldPath
    reason: str


class ProgressView(BaseModel):
    completed: int
    total: int


class SessionView(BaseModel):
    id: str
    version: int
    fields: list[FieldView]
    state: dict[str, Any]  # flat view of confirmed values, as in the brief
    messages: list[MessageView]
    document_markdown: str
    progress: ProgressView
    is_complete: bool
    focus: FieldPath | None
    next_question: str


class TurnResult(SessionView):
    reply: str
    changes: list[ChangeView]
    rejected_updates: list[RejectedUpdateView]
    warnings: list[str]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    provider: str
    model_configured: bool


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool


class ErrorEnvelope(BaseModel):
    error: ErrorBody


def session_view(session: Session) -> SessionView:
    state = session.state
    done = progress(state)
    return SessionView(
        id=session.id,
        version=session.version,
        fields=[_field_view(path, session) for path in FIELD_PATHS],
        state=state.as_plain(),
        messages=[MessageView(role=m.role, content=m.content) for m in session.messages],
        document_markdown=render(state),
        progress=ProgressView(completed=done.completed, total=done.total),
        is_complete=is_complete(state),
        focus=next_focus(state),
        next_question=planner_question(state),
    )


def turn_result(session: Session, outcome: TurnOutcome) -> TurnResult:
    return TurnResult(
        **session_view(session).model_dump(),
        reply=outcome.reply,
        changes=[
            ChangeView(
                path=c.path,
                label=FIELD_LABELS[c.path],
                old_value=_jsonable(c.old_value),
                new_value=_jsonable(c.new_value),
                old_status=c.old_status,
                new_status=c.new_status,
            )
            for c in outcome.changes
        ],
        rejected_updates=[
            RejectedUpdateView(path=r.update.path, reason=r.reason) for r in outcome.rejected
        ],
        warnings=list(outcome.warnings),
    )


def _field_view(path: FieldPath, session: Session) -> FieldView:
    field = session.state.get(path)
    return FieldView(
        path=path,
        label=FIELD_LABELS[path],
        value=_jsonable(field.value),
        status=field.status,
        candidate=_jsonable(field.candidate),
        note=field.note,
        source=field.source if field.status == FieldStatus.CAPTURED else None,
        source_turn=field.source_turn if field.status == FieldStatus.CAPTURED else None,
        evidence=field.evidence if field.status == FieldStatus.CAPTURED else None,
        previous_value=_jsonable(field.previous_value)
        if field.status == FieldStatus.CAPTURED
        else None,
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, BaseModel):
        return value.model_dump()
    return value
