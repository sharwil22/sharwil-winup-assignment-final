"""Deterministic Personal Wishes Document generator.

The document is rendered from `WishesState` by code and a Jinja2 template; no LLM is
involved, so the draft can only contain what the state contains. Missing and unclear
answers are shown as visible placeholders rather than filled with defaults.

All wording decisions live in `_build_context`; the template only lays the text out.
User-supplied text is Markdown-escaped so it cannot change the document's structure.
"""

import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.domain.models import FIELD_LABELS, FieldPath, FieldStatus, Gift, WishesState
from app.domain.planner import is_complete, progress

DISCLAIMER = (
    "FICTIONAL DRAFT — NOT LEGAL ADVICE. Generated for a technical exercise; "
    "this document has no legal effect."
)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
# Values always appear mid-sentence, so only inline markup needs escaping. Newlines are
# collapsed so a value can never start a new block (heading, list, quote).
_INLINE_MARKUP = re.compile(r"([\\`*_\[\]<>|~])")

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    undefined=StrictUndefined,  # a typo in the template fails loudly instead of rendering ""
    autoescape=False,  # Markdown output; escaping is done explicitly with `escape_markdown`
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def escape_markdown(text: str) -> str:
    return _INLINE_MARKUP.sub(r"\\\1", " ".join(text.split()))


def render(state: WishesState) -> str:
    return _env.get_template("wishes.md.j2").render(**_build_context(state))


def _build_context(state: WishesState) -> dict[str, Any]:
    done = progress(state)
    return {
        "disclaimer": DISCLAIMER,
        "status_line": (
            "Draft status: all sections complete"
            if is_complete(state)
            else f"Draft status: incomplete ({done.completed} of {done.total} answers complete)"
        ),
        "declarant": (
            f"I, {_text(state, 'full_name')}, of {_text(state, 'home_address')}, "
            "make this Personal Wishes Document."
        ),
        "scope": _scope(state),
        "children": _children(state),
        "executor": _executor(state),
        "gifts": _gifts(state),
        "additional_wishes": _additional_wishes(state),
    }


def _placeholder(path: FieldPath, state: WishesState) -> str:
    if state.get(path).status == FieldStatus.NEEDS_CLARIFICATION:
        return f"[Needs clarification: {FIELD_LABELS[path]}]"
    return f"[To be confirmed: {FIELD_LABELS[path]}]"


def _confirmed(path: FieldPath, state: WishesState) -> Any:
    """The confirmed value, or None while the field is missing or under clarification."""
    field = state.get(path)
    return field.value if field.status == FieldStatus.CAPTURED else None


def _text(state: WishesState, path: FieldPath) -> str:
    value = _confirmed(path, state)
    return _placeholder(path, state) if value is None else escape_markdown(value)


def _scope(state: WishesState) -> str:
    worldwide = _confirmed("covers_worldwide_assets", state)
    if worldwide is None:
        return _placeholder("covers_worldwide_assets", state)
    if worldwide:
        return "These wishes cover all of my assets worldwide."
    return "These wishes do not cover my assets outside my country of residence."


def _children(state: WishesState) -> str:
    has_children = _confirmed("has_children", state)
    if has_children is None:
        return _placeholder("has_children", state)
    if not has_children:
        return "I have no children."
    names = _confirmed("children_names", state)
    if names is None:
        return f"I have children. Their names are {_placeholder('children_names', state)}."
    return f"I have the following children: {_join([escape_markdown(n) for n in names])}."


def _executor(state: WishesState) -> str:
    name = _text(state, "executor.name")
    relationship = _confirmed("executor.relationship", state)
    if relationship is None:
        relation = f" (relationship: {_placeholder('executor.relationship', state)})"
    else:
        relation = f", my {escape_markdown(_strip_possessive(relationship))},"
    return f"I appoint {name}{relation} as executor of these wishes."


def _gifts(state: WishesState) -> list[str] | str:
    gifts: list[Gift] | None = _confirmed("specific_gifts", state)
    if gifts is None:
        return _placeholder("specific_gifts", state)
    if not gifts:
        return "I make no specific gifts."
    return [
        f"I leave {escape_markdown(_possessive_item(g.item))} to {escape_markdown(g.recipient)}."
        for g in gifts
    ]


def _additional_wishes(state: WishesState) -> str:
    wishes = _confirmed("additional_wishes", state)
    if wishes is None:
        return _placeholder("additional_wishes", state)
    return escape_markdown(wishes) if wishes else "I have no additional wishes."


# Items that already start with a determiner or a possessive ("Anna's ring") are kept as is.
_DETERMINER = re.compile(
    r"^((my|the|a|an|all|any|both|each|every|some|his|her|our)\b|\w+['’]s\b)", re.IGNORECASE
)


def _possessive_item(item: str) -> str:
    """ "car" -> "my car", but "my piano" or "the house" stay as they are."""
    item = item.strip()
    return item if _DETERMINER.match(item) else f"my {item}"


def _strip_possessive(relationship: str) -> str:
    """Avoid "my my brother" when the user's own words included "my"."""
    return re.sub(r"^my\s+", "", relationship.strip(), flags=re.IGNORECASE)


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
