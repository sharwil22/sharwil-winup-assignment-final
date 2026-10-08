from typing import Any

from app.domain import reducer
from app.domain.models import FieldPath, WishesState
from app.domain.updates import Certainty, ProposedUpdate, UpdateKind


def upd(
    path: FieldPath,
    value: Any,
    evidence: str = "",
    *,
    kind: UpdateKind = UpdateKind.NEW,
    certainty: Certainty = Certainty.EXPLICIT,
) -> ProposedUpdate:
    return ProposedUpdate(path=path, value=value, evidence=evidence, kind=kind, certainty=certainty)


def state_with(*updates: ProposedUpdate) -> WishesState:
    """Build a state by applying explicit updates on turn 1 (bypasses validation)."""
    return reducer.apply(WishesState.empty(), list(updates), turn=1).state
