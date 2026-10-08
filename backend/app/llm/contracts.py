"""The contract between the application and the model.

`TurnContext` is what we send; `TurnExtraction` is what the model must return. The JSON
schema sent to the API is generated from `TurnExtraction`, and every response is parsed
back through the same Pydantic model, so the contract is defined in exactly one place.

The contract is deliberately separate from the domain's `ProposedUpdate`: the model-facing
shape can change (field names, extra hints) without touching the domain rules.
"""

import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.domain.models import FieldPath, Gift, WishesState
from app.domain.updates import Certainty, ProposedUpdate, UpdateKind, UpdateSource


class _Strict(BaseModel):
    # extra="forbid" emits `additionalProperties: false`, which structured outputs require.
    model_config = ConfigDict(extra="forbid", frozen=True)


class GiftOut(_Strict):
    item: str
    recipient: str


class FieldUpdate(_Strict):
    path: FieldPath
    value: bool | str | list[str] | list[GiftOut]
    kind: Literal["new", "correction"]
    certainty: Literal["explicit", "unclear"]
    evidence: str

    def to_proposed(self) -> ProposedUpdate:
        value: Any = self.value
        if isinstance(value, list) and value and isinstance(value[0], GiftOut):
            value = [Gift(item=g.item, recipient=g.recipient) for g in value]
        return ProposedUpdate(
            path=self.path,
            value=value,
            kind=UpdateKind(self.kind),
            certainty=Certainty(self.certainty),
            evidence=self.evidence,
            source=UpdateSource.CHAT,
        )


class TurnExtraction(_Strict):
    updates: list[FieldUpdate]
    reply: str
    asks_about: FieldPath | None  # the field the reply's question is about, if any


EXTRACTION_SCHEMA: dict[str, Any] = TurnExtraction.model_json_schema()


@dataclass(frozen=True)
class HistoryMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class TurnContext:
    state: WishesState
    remaining: tuple[FieldPath, ...]  # unanswered or unclear fields, in interview order
    history: tuple[HistoryMessage, ...]  # recent messages, oldest first
    user_message: str
    repair_hint: str | None = None  # validation error from a previous malformed attempt


class LLMError(Exception):
    """Base class for model failures."""


class LLMUnavailable(LLMError):
    """Timeout, rate limit, network or server error. Retryable later; state stays unchanged."""


class LLMNotConfigured(LLMError):
    """The selected provider is missing configuration, e.g. an API key."""


class LLMMalformedOutput(LLMError):
    """The model answered, but not in the contract's shape."""

    def __init__(self, message: str, raw: str | None = None) -> None:
        super().__init__(message)
        self.raw = raw


class LLMRefused(LLMError):
    """The model declined to answer (safety stop). Not worth retrying with the same input."""


def parse_extraction(raw: str | None) -> TurnExtraction:
    """Parse raw model text into a `TurnExtraction`, or raise `LLMMalformedOutput`."""
    if raw is None or not raw.strip():
        raise LLMMalformedOutput("empty response", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMMalformedOutput(f"invalid JSON: {exc.msg}", raw) from exc
    try:
        return TurnExtraction.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()[:5]
        )
        raise LLMMalformedOutput(f"does not match contract: {problems}", raw) from exc
