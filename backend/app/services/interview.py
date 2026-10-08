"""Runs one user turn: plan → model → validate → reduce → reply.

This is the only place that combines the model with the domain rules. It never mutates
state: it returns a `TurnOutcome` and the caller decides whether to persist it. If the
model is unavailable or not configured, the error propagates and no state change exists.

Failure policy
- Malformed model output: retry once with the parse error as a hint; if it fails again,
  keep the state unchanged and ask the planner's question.
- Refusal: keep the state unchanged and ask the planner's question.
- Unavailable / not configured: raise; the API reports it and the state is untouched.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.domain import reducer
from app.domain.models import FieldPath, FieldStatus, WishesState
from app.domain.planner import COMPLETION_MESSAGE, next_focus, open_fields, question_for
from app.domain.reducer import Change, Conflict
from app.domain.validation import Rejection, validate_updates
from app.llm.contracts import (
    HistoryMessage,
    LLMMalformedOutput,
    LLMRefused,
    TurnContext,
    TurnExtraction,
)
from app.llm.interface import LLMProvider

HISTORY_LIMIT = 10

GREETING = (
    "Hello! I'll help you prepare a draft Personal Wishes Document. It's fictional and not "
    "legal advice. Answer in your own words, and you can correct anything at any time."
)

# Warning codes returned to the API caller (shown in the UI as quiet notices).
WARN_RETRIED = "malformed_output_retried"
WARN_FALLBACK = "malformed_output_fallback"
WARN_REFUSED = "model_refused"
WARN_REPLY_REPLACED = "reply_replaced"
WARN_UPDATES_REJECTED = "updates_rejected"


@dataclass(frozen=True)
class TurnOutcome:
    state: WishesState
    reply: str
    focus: FieldPath | None
    changes: tuple[Change, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    rejected: tuple[Rejection, ...] = ()
    warnings: tuple[str, ...] = ()


def opening_message(state: WishesState) -> str:
    return f"{GREETING} {planner_question(state)}"


def planner_question(state: WishesState) -> str:
    focus = next_focus(state)
    return COMPLETION_MESSAGE if focus is None else question_for(focus, state)


def handle_turn(
    provider: LLMProvider,
    state: WishesState,
    history: Sequence[HistoryMessage],
    user_message: str,
    turn: int,
) -> TurnOutcome:
    ctx = TurnContext(
        state=state,
        remaining=open_fields(state),
        history=tuple(history[-HISTORY_LIMIT:]),
        user_message=user_message,
    )
    warnings: list[str] = []

    try:
        extraction = _extract_with_repair(provider, ctx, warnings)
    except LLMRefused:
        warnings.append(WARN_REFUSED)
        extraction = None
    if extraction is None:
        reply = f"Sorry, I couldn't process that answer. {planner_question(state)}"
        return TurnOutcome(state, reply, next_focus(state), warnings=tuple(warnings))

    proposed = [update.to_proposed() for update in extraction.updates]
    validation = validate_updates(proposed, state, user_message)
    if validation.rejected:
        warnings.append(WARN_UPDATES_REJECTED)
    result = reducer.apply(state, list(validation.accepted), turn)

    focus = next_focus(result.state)
    reply = _compose_reply(extraction, result, validation.rejected, focus, warnings)
    return TurnOutcome(
        state=result.state,
        reply=reply,
        focus=focus,
        changes=result.changes,
        conflicts=result.conflicts,
        rejected=validation.rejected,
        warnings=tuple(warnings),
    )


def _extract_with_repair(
    provider: LLMProvider, ctx: TurnContext, warnings: list[str]
) -> TurnExtraction | None:
    try:
        return provider.extract(ctx)
    except LLMMalformedOutput as first:
        warnings.append(WARN_RETRIED)
        try:
            return provider.extract(replace(ctx, repair_hint=str(first)))
        except LLMMalformedOutput:
            warnings.append(WARN_FALLBACK)
            return None


def _compose_reply(
    extraction: TurnExtraction,
    result: reducer.ReduceResult,
    rejected: tuple[Rejection, ...],
    focus: FieldPath | None,
    warnings: list[str],
) -> str:
    """Use the model's wording only when it asks exactly what the planner would ask.

    The planner decides *what* to ask; the model may decide *how*. Its reply is replaced
    when it targets a different field (e.g. one already captured), when a conflict needs the
    precise clarification question, or when some of its updates were rejected (its
    acknowledgement could then claim something we did not record).
    """
    model_reply = extraction.reply.strip()
    trusted = (
        bool(model_reply)
        and extraction.asks_about == focus
        and not result.conflicts
        and not rejected
    )
    if trusted:
        return model_reply

    if model_reply:
        warnings.append(WARN_REPLY_REPLACED)
    question = COMPLETION_MESSAGE if focus is None else question_for(focus, result.state)
    # Acknowledge only what was actually recorded; an answer held for clarification wasn't.
    recorded = any(c.new_status == FieldStatus.CAPTURED for c in result.changes)
    if result.conflicts or not recorded or focus is None:
        return question
    return f"Thanks, I've noted that. {question}"
