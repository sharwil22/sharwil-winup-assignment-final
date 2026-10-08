"""Structured state for the Personal Wishes interview.

`WishesState` is the application's source of truth. Every field carries a status so
unknown, unclear and not-applicable values are explicit rather than implied by `None`.

Invariant: `Field.value` only ever holds a value the user has confirmed. Unclear or
conflicting proposals wait in `Field.candidate` until they are resolved.
"""

from enum import StrEnum
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField


class FieldStatus(StrEnum):
    MISSING = "missing"
    NEEDS_CLARIFICATION = "needs_clarification"
    CAPTURED = "captured"
    NOT_APPLICABLE = "not_applicable"


class Field[T](BaseModel):
    model_config = ConfigDict(frozen=True)

    value: T | None = None
    status: FieldStatus = FieldStatus.MISSING
    candidate: T | None = None  # proposed value awaiting clarification
    note: str | None = None  # why clarification is needed
    # Provenance of `value`: shown to the user so every answer is traceable to their words.
    source_turn: int | None = None  # user turn that set `value`
    source: Literal["chat", "edit"] | None = None
    evidence: str | None = None  # the user's own words that support `value` (chat only)
    previous_value: T | None = None  # the value a correction replaced, if any


class Gift(BaseModel):
    model_config = ConfigDict(frozen=True)

    item: str
    recipient: str


class Executor(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: Field[str] = PydanticField(default_factory=Field[str])
    relationship: Field[str] = PydanticField(default_factory=Field[str])


FieldPath = Literal[
    "full_name",
    "home_address",
    "covers_worldwide_assets",
    "has_children",
    "children_names",
    "executor.name",
    "executor.relationship",
    "specific_gifts",
    "additional_wishes",
]

# Interview order: the planner asks about fields in this sequence.
FIELD_PATHS: tuple[FieldPath, ...] = get_args(FieldPath)

FIELD_LABELS: dict[FieldPath, str] = {
    "full_name": "full name",
    "home_address": "home address",
    "covers_worldwide_assets": "whether the document covers worldwide assets",
    "has_children": "whether you have children",
    "children_names": "children's names",
    "executor.name": "executor's name",
    "executor.relationship": "executor's relationship to you",
    "specific_gifts": "specific gifts",
    "additional_wishes": "additional wishes",
}

BOOL_PATHS: frozenset[FieldPath] = frozenset({"covers_worldwide_assets", "has_children"})
# Optional fields: an empty value with status CAPTURED means the user said "none".
OPTIONAL_PATHS: frozenset[FieldPath] = frozenset({"specific_gifts", "additional_wishes"})


class WishesState(BaseModel):
    model_config = ConfigDict(frozen=True)

    full_name: Field[str] = PydanticField(default_factory=Field[str])
    home_address: Field[str] = PydanticField(default_factory=Field[str])
    covers_worldwide_assets: Field[bool] = PydanticField(default_factory=Field[bool])
    has_children: Field[bool] = PydanticField(default_factory=Field[bool])
    children_names: Field[list[str]] = PydanticField(default_factory=Field[list[str]])
    executor: Executor = PydanticField(default_factory=Executor)
    specific_gifts: Field[list[Gift]] = PydanticField(default_factory=Field[list[Gift]])
    additional_wishes: Field[str] = PydanticField(default_factory=Field[str])
    version: int = 0

    @classmethod
    def empty(cls) -> "WishesState":
        return cls()

    def get(self, path: FieldPath) -> Field[Any]:
        if path.startswith("executor."):
            field: Field[Any] = getattr(self.executor, path.removeprefix("executor."))
        else:
            field = getattr(self, path)
        return field

    def with_field(self, path: FieldPath, field: Field[Any]) -> "WishesState":
        """Return a copy with one field replaced; the original is never mutated."""
        if path.startswith("executor."):
            executor = self.executor.model_copy(update={path.removeprefix("executor."): field})
            return self.model_copy(update={"executor": executor})
        return self.model_copy(update={path: field})

    def as_plain(self) -> dict[str, Any]:
        """Flat view of confirmed values, shaped like the brief's example. Unknown = None."""
        gifts = self.specific_gifts.value
        return {
            "full_name": self.full_name.value,
            "home_address": self.home_address.value,
            "covers_worldwide_assets": self.covers_worldwide_assets.value,
            "has_children": self.has_children.value,
            "children_names": self.children_names.value,
            "executor": {
                "name": self.executor.name.value,
                "relationship": self.executor.relationship.value,
            },
            "specific_gifts": None if gifts is None else [g.model_dump() for g in gifts],
            "additional_wishes": self.additional_wishes.value,
        }
