"""Proposed changes to the state.

A `ProposedUpdate` is what the LLM (or a direct UI edit) suggests. It is never applied
directly: it goes through `validation.validate_updates` and then `reducer.apply`.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.domain.models import FieldPath, Gift

UpdateValue = bool | str | list[str] | list[Gift]


class UpdateKind(StrEnum):
    NEW = "new"  # first answer for a field
    CORRECTION = "correction"  # user explicitly changes an earlier answer


class Certainty(StrEnum):
    EXPLICIT = "explicit"
    UNCLEAR = "unclear"  # vague or partial; must be clarified before it is captured


class UpdateSource(StrEnum):
    CHAT = "chat"
    UI_EDIT = "ui_edit"


class ProposedUpdate(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: FieldPath
    value: UpdateValue
    kind: UpdateKind = UpdateKind.NEW
    certainty: Certainty = Certainty.EXPLICIT
    evidence: str = ""  # the user's own words supporting the value
    source: UpdateSource = UpdateSource.CHAT
