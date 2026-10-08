import os
from pathlib import Path

import pytest

from app.documents.generator import DISCLAIMER, escape_markdown, render
from app.domain.models import FIELD_LABELS, FIELD_PATHS, Gift, WishesState
from app.domain.reducer import apply
from app.domain.updates import Certainty
from tests.helpers import state_with, upd

SNAPSHOTS = Path(__file__).parent / "snapshots"

COMPLETE = state_with(
    upd("full_name", "Jane Smith"),
    upd("home_address", "4 High Street, Leeds LS1 1AA"),
    upd("covers_worldwide_assets", True),
    upd("has_children", True),
    upd("children_names", ["Tom Smith", "Ann Smith"]),
    upd("executor.name", "James Smith"),
    upd("executor.relationship", "brother"),
    upd("specific_gifts", [Gift(item="my car", recipient="Tom Smith")]),
    upd("additional_wishes", "I would like a small, quiet funeral."),
)

PARTIAL = apply(
    state_with(
        upd("full_name", "Jane Smith"),
        upd("covers_worldwide_assets", False),
        upd("has_children", False),
        upd("executor.name", "James Smith"),
    ),
    [upd("home_address", "London", "somewhere in London", certainty=Certainty.UNCLEAR)],
    turn=2,
).state


def assert_matches_snapshot(name: str, text: str) -> None:
    """Compare with tests/snapshots/<name>.md. Run with UPDATE_SNAPSHOTS=1 to rewrite."""
    path = SNAPSHOTS / f"{name}.md"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert path.exists(), f"missing snapshot {path}; run with UPDATE_SNAPSHOTS=1"
    assert text == path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("name", "state"),
    [("empty", WishesState.empty()), ("partial", PARTIAL), ("complete", COMPLETE)],
)
def test_document_matches_snapshot(name: str, state: WishesState) -> None:
    assert_matches_snapshot(name, render(state))


@pytest.mark.parametrize("state", [WishesState.empty(), PARTIAL, COMPLETE])
def test_disclaimer_is_at_the_top_and_bottom_of_every_draft(state: WishesState) -> None:
    lines = render(state).strip().splitlines()
    assert lines[0] == f"> **{DISCLAIMER}**"
    assert lines[-1] == f"> **{DISCLAIMER}**"


def test_empty_state_shows_a_placeholder_for_every_field() -> None:
    doc = render(WishesState.empty())
    for path in FIELD_PATHS:
        if path == "children_names":
            continue  # only asked once the user says they have children
        assert f"[To be confirmed: {FIELD_LABELS[path]}]" in doc
    assert "Draft status: incomplete (0 of 9 answers complete)" in doc


def test_unclear_answer_is_not_used_in_the_document() -> None:
    doc = render(PARTIAL)
    assert "London" not in doc
    assert "[Needs clarification: home address]" in doc


def test_conflicting_answer_shows_clarification_not_either_value() -> None:
    state = apply(state_with(upd("executor.name", "James")), [upd("executor.name", "Anna")], 2)
    doc = render(state.state)
    assert "[Needs clarification: executor's name]" in doc
    assert "James" not in doc
    assert "Anna" not in doc


def test_complete_state_is_marked_complete() -> None:
    doc = render(COMPLETE)
    assert "Draft status: all sections complete" in doc
    assert "To be confirmed" not in doc
    assert "Needs clarification" not in doc


def test_none_answers_render_as_explicit_statements() -> None:
    state = state_with(upd("specific_gifts", []), upd("additional_wishes", ""))
    doc = render(state)
    assert "I make no specific gifts." in doc
    assert "I have no additional wishes." in doc


def test_relationship_with_my_prefix_is_not_doubled() -> None:
    state = state_with(upd("executor.name", "James"), upd("executor.relationship", "my brother"))
    assert "I appoint James, my brother, as executor" in render(state)


def test_user_text_cannot_inject_markdown_structure() -> None:
    state = state_with(upd("full_name", "*Bob*\n# Heading <script>"))
    doc = render(state)
    assert "I, \\*Bob\\* # Heading \\<script\\>, of" in doc
    assert "\n# Heading" not in doc


def test_rendering_is_deterministic() -> None:
    assert render(COMPLETE) == render(COMPLETE)


def test_escape_markdown_leaves_ordinary_punctuation_alone() -> None:
    assert escape_markdown("4 High St. Smith-Jones (flat 2)") == "4 High St. Smith-Jones (flat 2)"


def test_gift_items_read_naturally_without_doubling_my() -> None:
    gifts = [
        Gift(item="car", recipient="Tom"),
        Gift(item="my piano", recipient="Ann"),
        Gift(item="Anna's ring", recipient="Ella"),
    ]
    doc = render(state_with(upd("specific_gifts", gifts)))
    assert "- I leave my car to Tom." in doc
    assert "- I leave my piano to Ann." in doc
    assert "- I leave Anna's ring to Ella." in doc
