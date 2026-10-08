"""Semantic validation of proposed updates.

Shape validation (is this a well-formed `ProposedUpdate`?) is done by Pydantic. This
module checks meaning: does the value fit the field, is it grounded in what the user
actually said, and is it consistent with the current state? Accepted updates come back
normalised; rejected ones come back with a reason so the caller can report them.
"""

from dataclasses import dataclass

from app.domain.models import BOOL_PATHS, OPTIONAL_PATHS, FieldStatus, Gift, WishesState
from app.domain.updates import ProposedUpdate, UpdateSource, UpdateValue
from app.domain.values import clean_text, comparable_text


@dataclass(frozen=True)
class Rejection:
    update: ProposedUpdate
    reason: str


@dataclass(frozen=True)
class ValidationResult:
    accepted: tuple[ProposedUpdate, ...]
    rejected: tuple[Rejection, ...]


def validate_updates(
    updates: list[ProposedUpdate], state: WishesState, user_message: str
) -> ValidationResult:
    accepted: list[ProposedUpdate] = []
    rejected: list[Rejection] = []
    seen_paths: set[str] = set()
    sets_children_true = any(u.path == "has_children" and u.value is True for u in updates)

    for update in updates:
        if update.path in seen_paths:
            rejected.append(Rejection(update, f"duplicate update for '{update.path}' in one turn"))
            continue
        seen_paths.add(update.path)

        normalised = _normalise_value(update)
        if isinstance(normalised, _Invalid):
            rejected.append(Rejection(update, normalised.reason))
            continue
        candidate = update.model_copy(update={"value": normalised})

        reason = _check_evidence(candidate, user_message) or _check_dependencies(
            candidate, state, sets_children_true
        )
        if reason:
            rejected.append(Rejection(update, reason))
        else:
            accepted.append(candidate)

    return ValidationResult(tuple(accepted), tuple(rejected))


@dataclass(frozen=True)
class _Invalid:
    reason: str


def _normalise_value(update: ProposedUpdate) -> UpdateValue | _Invalid:
    path, value = update.path, update.value

    if path in BOOL_PATHS:
        return value if isinstance(value, bool) else _Invalid(f"'{path}' must be true or false")

    if path == "children_names":
        if not isinstance(value, list) or not value:
            return _Invalid("'children_names' must be a non-empty list of names")
        names = [clean_text(n) for n in value if isinstance(n, str)]
        if len(names) != len(value) or not all(names):
            return _Invalid("'children_names' must contain only non-empty names")
        return names

    if path == "specific_gifts":
        if not isinstance(value, list):
            return _Invalid("'specific_gifts' must be a list of {item, recipient}")
        gifts: list[Gift] = []
        for gift in value:
            if not isinstance(gift, Gift):
                return _Invalid("'specific_gifts' must be a list of {item, recipient}")
            item, recipient = clean_text(gift.item), clean_text(gift.recipient)
            if not item or not recipient:
                return _Invalid("each gift needs both an item and a recipient")
            gifts.append(Gift(item=item, recipient=recipient))
        return gifts

    # Remaining paths are text fields.
    if not isinstance(value, str):
        return _Invalid(f"'{path}' must be text")
    text = clean_text(value)
    if not text and path not in OPTIONAL_PATHS:
        return _Invalid(f"'{path}' must not be empty")
    return text


def _check_evidence(update: ProposedUpdate, user_message: str) -> str | None:
    """Guard against invented facts: chat updates must quote the user's own words."""
    if update.source == UpdateSource.UI_EDIT:
        return None
    evidence = comparable_text(update.evidence)
    if not evidence:
        return "no evidence quoted from the user's message"
    if evidence not in comparable_text(user_message):
        return "evidence does not appear in the user's message"
    return None


def _check_dependencies(
    update: ProposedUpdate, state: WishesState, sets_children_true: bool
) -> str | None:
    if update.path != "children_names":
        return None
    has_children = state.has_children
    said_no = has_children.status == FieldStatus.CAPTURED and has_children.value is False
    if said_no and not sets_children_true:
        return "children's names given while 'has_children' is no"
    return None
