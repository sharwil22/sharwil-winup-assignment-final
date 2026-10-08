"""Decides what to ask next, deterministically.

The server, not the model, chooses the next question. The model is told the focus and may
phrase it, but the planner's templated question is the fallback whenever the model's
reply is unusable or asks about something already captured.
"""

from dataclasses import dataclass
from typing import Any

from app.domain.models import (
    BOOL_PATHS,
    FIELD_LABELS,
    FIELD_PATHS,
    Field,
    FieldPath,
    FieldStatus,
    WishesState,
)
from app.domain.values import format_value

DONE_STATUSES = frozenset({FieldStatus.CAPTURED, FieldStatus.NOT_APPLICABLE})

COMPLETION_MESSAGE = (
    "Thank you, that's everything I need. Please review the draft document. "
    "You can still correct any answer."
)

_QUESTIONS: dict[FieldPath, str] = {
    "full_name": "What is your full name?",
    "home_address": "What is your home address?",
    "covers_worldwide_assets": "Should this document cover all of your assets worldwide?",
    "has_children": "Do you have any children?",
    "children_names": "What are your children's names?",
    "executor.name": "Who would you like to appoint as your executor?",
    "executor.relationship": "What is your executor's relationship to you?",
    "specific_gifts": (
        "Are there any specific gifts you would like to leave, such as an item to a "
        "particular person? You can say none."
    ),
    "additional_wishes": "Do you have any additional wishes to include? You can say none.",
}


@dataclass(frozen=True)
class Progress:
    completed: int
    total: int


def next_focus(state: WishesState) -> FieldPath | None:
    """First field needing clarification, else first missing field, in interview order."""
    fields = open_fields(state)
    return fields[0] if fields else None


def open_fields(state: WishesState) -> tuple[FieldPath, ...]:
    """Fields still to settle, in the order the planner will ask about them."""
    unclear = [p for p in FIELD_PATHS if state.get(p).status == FieldStatus.NEEDS_CLARIFICATION]
    missing = [p for p in FIELD_PATHS if state.get(p).status == FieldStatus.MISSING]
    return (*unclear, *missing)


def question_for(path: FieldPath, state: WishesState) -> str:
    field = state.get(path)
    if field.status == FieldStatus.NEEDS_CLARIFICATION:
        return _clarification_question(path, field)
    if path == "executor.relationship" and state.executor.name.status == FieldStatus.CAPTURED:
        return f"What is {state.executor.name.value}'s relationship to you?"
    return _QUESTIONS[path]


def next_question(state: WishesState) -> str:
    path = next_focus(state)
    return COMPLETION_MESSAGE if path is None else question_for(path, state)


def progress(state: WishesState) -> Progress:
    completed = sum(1 for path in FIELD_PATHS if state.get(path).status in DONE_STATUSES)
    return Progress(completed=completed, total=len(FIELD_PATHS))


def is_complete(state: WishesState) -> bool:
    return next_focus(state) is None


def _clarification_question(path: FieldPath, field: Field[Any]) -> str:
    label = FIELD_LABELS[path]
    if field.value is not None and field.candidate is not None:
        return (
            f'Earlier you gave "{format_value(field.value)}" for {label}, but now '
            f'"{format_value(field.candidate)}". Which is correct?'
        )
    if path in BOOL_PATHS:
        return f"Sorry, I didn't quite catch that. {_QUESTIONS[path]} Please answer yes or no."
    if path == "home_address":
        return "Could you give your full home address, including the street, town and postcode?"
    if field.candidate is not None:
        return (
            f'Just to check your {label}: you said "{format_value(field.candidate)}". '
            "Could you confirm or give a bit more detail?"
        )
    return f"Could you clarify your {label}?"
