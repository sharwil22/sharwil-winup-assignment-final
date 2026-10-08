"""Pure state transitions: (state, validated updates) -> new state + what changed.

Rules
- An `unclear` update never becomes CAPTURED: it waits in `candidate` with status
  NEEDS_CLARIFICATION, and any confirmed `value` is kept.
- A `new` update on a MISSING or NEEDS_CLARIFICATION field is captured. This is also how
  a pending clarification is resolved.
- A `new` update that differs from a CAPTURED value is a conflict: the confirmed value
  stays, the proposal waits in `candidate`, and the user is asked which is right.
- A `correction` overwrites, whatever the current status.
- Repeating the captured value changes nothing.
- `has_children` drives `children_names`: "no" makes it NOT_APPLICABLE, "yes" reopens it.
  Names given while `has_children` is unanswered imply "yes"; names given while a
  `has_children` conflict is open wait until it is resolved.
- `version` goes up by one when anything changed.
"""

from dataclasses import dataclass
from typing import Any

from app.domain.models import FIELD_LABELS, FIELD_PATHS, Field, FieldPath, FieldStatus, WishesState
from app.domain.updates import Certainty, ProposedUpdate, UpdateKind, UpdateSource
from app.domain.values import format_value, same_value


@dataclass(frozen=True)
class Change:
    path: FieldPath
    old_value: Any
    new_value: Any
    old_status: FieldStatus
    new_status: FieldStatus
    turn: int


@dataclass(frozen=True)
class Conflict:
    path: FieldPath
    current: Any
    proposed: Any


@dataclass(frozen=True)
class ReduceResult:
    state: WishesState
    changes: tuple[Change, ...]
    conflicts: tuple[Conflict, ...]


def apply(state: WishesState, updates: list[ProposedUpdate], turn: int) -> ReduceResult:
    reducer = _Reducer(state, turn)
    # Fixed order so has_children is settled before children_names, whatever the input order.
    for update in sorted(updates, key=lambda u: FIELD_PATHS.index(u.path)):
        reducer.apply(update)
    return reducer.result()


class _Reducer:
    def __init__(self, state: WishesState, turn: int) -> None:
        self.original = state
        self.state = state
        self.turn = turn
        self.changes: list[Change] = []
        self.conflicts: list[Conflict] = []

    def result(self) -> ReduceResult:
        state = self.state
        if self.changes:
            state = state.model_copy(update={"version": self.original.version + 1})
        return ReduceResult(state, tuple(self.changes), tuple(self.conflicts))

    def apply(self, update: ProposedUpdate) -> None:
        if update.path == "children_names":
            self._apply_children_names(update)
        else:
            self._set(update.path, self._next_field(update))
        if update.path == "has_children":
            self._sync_children_names()

    def _next_field(self, update: ProposedUpdate) -> Field[Any]:
        current = self.state.get(update.path)

        if current.status == FieldStatus.CAPTURED and same_value(current.value, update.value):
            return current

        if update.certainty == Certainty.UNCLEAR:
            return current.model_copy(
                update={
                    "status": FieldStatus.NEEDS_CLARIFICATION,
                    "candidate": update.value,
                    "note": f'Unclear answer: "{update.evidence or format_value(update.value)}"',
                }
            )

        if update.kind == UpdateKind.CORRECTION or current.status != FieldStatus.CAPTURED:
            replaced = current.value is not None and not same_value(current.value, update.value)
            return current.model_copy(
                update={
                    "value": update.value,
                    "status": FieldStatus.CAPTURED,
                    "candidate": None,
                    "note": None,
                    **_provenance(update, self.turn),
                    "previous_value": current.value if replaced else None,
                }
            )

        self.conflicts.append(Conflict(update.path, current.value, update.value))
        return current.model_copy(
            update={
                "status": FieldStatus.NEEDS_CLARIFICATION,
                "candidate": update.value,
                "note": (
                    f"Conflicts with earlier answer for {FIELD_LABELS[update.path]}: "
                    f"{format_value(current.value)}"
                ),
            }
        )

    def _apply_children_names(self, update: ProposedUpdate) -> None:
        has_children = self.state.has_children
        confirmed_yes = has_children.status == FieldStatus.CAPTURED and has_children.value is True
        pending_yes = (
            has_children.status == FieldStatus.NEEDS_CLARIFICATION
            and has_children.candidate is True
        )

        if confirmed_yes:
            self._set("children_names", self._next_field(update))
        elif pending_yes:
            self._set(
                "children_names",
                self.state.children_names.model_copy(
                    update={
                        "status": FieldStatus.NEEDS_CLARIFICATION,
                        "candidate": update.value,
                        "note": "Waiting to confirm whether you have children",
                    }
                ),
            )
        elif has_children.status == FieldStatus.MISSING:
            names = self._next_field(update)
            self._set("children_names", names)
            if names.status == FieldStatus.CAPTURED:
                self._set(
                    "has_children",
                    Field[bool](
                        value=True,
                        status=FieldStatus.CAPTURED,
                        note="Implied by the children's names given",
                        **_provenance(update, self.turn),
                    ),
                )
        # has_children is "no": validation rejects names, so there is nothing to do here.

    def _sync_children_names(self) -> None:
        has_children = self.state.has_children
        names = self.state.children_names
        if has_children.status != FieldStatus.CAPTURED:
            return
        if has_children.value is False:
            self._set("children_names", Field[list[str]](status=FieldStatus.NOT_APPLICABLE))
        elif names.status == FieldStatus.NOT_APPLICABLE:
            self._set("children_names", Field[list[str]]())

    def _set(self, path: FieldPath, field: Field[Any]) -> None:
        current = self.state.get(path)
        if field == current:
            return
        self.state = self.state.with_field(path, field)
        self.changes.append(
            Change(path, current.value, field.value, current.status, field.status, self.turn)
        )


def _provenance(update: ProposedUpdate, turn: int) -> dict[str, Any]:
    edited = update.source == UpdateSource.UI_EDIT
    return {
        "source_turn": turn,
        "source": "edit" if edited else "chat",
        "evidence": None if edited else (update.evidence or None),
    }
