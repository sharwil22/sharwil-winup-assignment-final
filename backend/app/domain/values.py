"""Helpers for comparing and displaying field values."""

import re
from typing import Any

from app.domain.models import Gift

_WHITESPACE = re.compile(r"\s+")
_EDGE_PUNCTUATION = " \t\n.,;:!?\"'`“”‘’"


def clean_text(text: str) -> str:
    """Trim and collapse internal whitespace, keeping the user's casing."""
    return _WHITESPACE.sub(" ", text).strip()


def comparable_text(text: str) -> str:
    """Case- and whitespace-insensitive form used for equality and evidence checks."""
    return clean_text(text).strip(_EDGE_PUNCTUATION).casefold()


def same_value(a: Any, b: Any) -> bool:
    return bool(_comparable(a) == _comparable(b))


def _comparable(value: Any) -> Any:
    if isinstance(value, str):
        return comparable_text(value)
    if isinstance(value, Gift):
        return (comparable_text(value.item), comparable_text(value.recipient))
    if isinstance(value, list):
        return [_comparable(v) for v in value]
    return value


def format_value(value: Any) -> str:
    """Human-readable form for questions and change logs."""
    if value is None:
        return "not given"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        if not value:
            return "none"
        parts = [f"{g.item} to {g.recipient}" if isinstance(g, Gift) else str(g) for g in value]
        return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    if value == "":
        return "none"
    return str(value)
