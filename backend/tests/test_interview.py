"""The full turn pipeline, driven by recorded model responses (fixtures)."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.models import FieldStatus, Gift, WishesState
from app.llm.contracts import LLMNotConfigured, LLMRefused, LLMUnavailable
from app.llm.mock_provider import ScriptedProvider
from app.services.interview import (
    WARN_FALLBACK,
    WARN_REFUSED,
    WARN_REPLY_REPLACED,
    WARN_RETRIED,
    WARN_UPDATES_REJECTED,
    TurnOutcome,
    handle_turn,
    opening_message,
)
from tests.helpers import state_with, upd

FIXTURES = Path(__file__).parent / "fixtures" / "llm_responses"

_NAME = upd("full_name", "Jane Smith")
_BEFORE_CHILDREN = (
    _NAME,
    upd("home_address", "4 High Street, Leeds LS1 1AA"),
    upd("covers_worldwide_assets", True),
)
_BEFORE_EXECUTOR = (*_BEFORE_CHILDREN, upd("has_children", False))

STATES: dict[str, WishesState] = {
    "empty": WishesState.empty(),
    "name_only": state_with(_NAME),
    "no_children": state_with(_NAME, upd("has_children", False)),
    "before_children": state_with(*_BEFORE_CHILDREN),
    "before_executor": state_with(*_BEFORE_EXECUTOR),
    "executor_james": state_with(
        *_BEFORE_EXECUTOR, upd("executor.name", "James"), upd("executor.relationship", "brother")
    ),
}


def run_fixture(name: str) -> tuple[WishesState, TurnOutcome, ScriptedProvider]:
    fixture: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text())
    before = STATES[fixture["state"]]
    provider = ScriptedProvider(fixture["raw_responses"])
    outcome = handle_turn(provider, before, [], fixture["user_message"], turn=2)
    return before, outcome, provider


def test_every_fixture_file_is_covered_by_a_test() -> None:
    names = {p.stem for p in FIXTURES.glob("*.json")}
    tested = {
        "valid_single",
        "valid_multi",
        "executor_relationship",
        "ambiguous_address",
        "correction_executor",
        "contradiction_children",
        "invented_fact",
        "reply_asks_captured",
        "wrong_types",
        "malformed_then_valid",
        "malformed_twice",
        "empty_response",
    }
    assert names == tested


def test_valid_single_answer_is_captured_and_model_reply_is_kept() -> None:
    _, outcome, _ = run_fixture("valid_single")
    assert outcome.state.full_name.value == "Jane Smith"
    assert outcome.focus == "home_address"
    assert outcome.reply == "Thanks, Jane. What is your home address?"
    assert outcome.warnings == ()


def test_several_fields_in_one_message_are_all_captured() -> None:
    _, outcome, _ = run_fixture("valid_multi")
    plain = outcome.state.as_plain()
    assert plain["full_name"] == "Jane Smith"
    assert plain["home_address"] == "4 High Street, Leeds LS1 1AA"
    assert plain["has_children"] is False
    assert outcome.state.children_names.status == FieldStatus.NOT_APPLICABLE
    assert outcome.focus == "covers_worldwide_assets"
    assert outcome.reply.endswith("Should this document cover all of your assets worldwide?")


def test_my_brother_james_fills_name_and_relationship() -> None:
    _, outcome, _ = run_fixture("executor_relationship")
    assert outcome.state.as_plain()["executor"] == {"name": "James", "relationship": "brother"}


def test_vague_address_is_held_for_clarification_not_captured() -> None:
    _, outcome, _ = run_fixture("ambiguous_address")
    field = outcome.state.home_address
    assert field.status == FieldStatus.NEEDS_CLARIFICATION
    assert field.value is None
    assert field.candidate == "London"
    assert outcome.focus == "home_address"


def test_correction_overwrites_the_executor() -> None:
    before, outcome, _ = run_fixture("correction_executor")
    assert before.executor.name.value == "James"
    assert outcome.state.as_plain()["executor"] == {"name": "Anna", "relationship": "sister"}
    assert {c.path for c in outcome.changes} == {"executor.name", "executor.relationship"}
    assert outcome.conflicts == ()


def test_contradiction_is_flagged_and_the_precise_question_is_asked() -> None:
    _, outcome, _ = run_fixture("contradiction_children")
    state = outcome.state
    assert state.has_children.value is False  # confirmed answer kept
    assert state.has_children.status == FieldStatus.NEEDS_CLARIFICATION
    assert state.children_names.candidate == ["Tom"]
    assert state.specific_gifts.value == [Gift(item="car", recipient="Tom")]
    assert outcome.focus == "has_children"
    assert outcome.reply == (
        'Earlier you gave "no" for whether you have children, but now "yes". Which is correct?'
    )
    assert WARN_REPLY_REPLACED in outcome.warnings


def test_invented_fact_is_rejected_and_reply_does_not_repeat_it() -> None:
    before, outcome, _ = run_fixture("invented_fact")
    assert outcome.state == before
    [rejection] = outcome.rejected
    assert rejection.reason == "evidence does not appear in the user's message"
    assert "Smith" not in outcome.reply
    assert outcome.reply == "What is your full name?"
    assert WARN_UPDATES_REJECTED in outcome.warnings


def test_reply_asking_about_a_captured_field_is_replaced() -> None:
    _, outcome, _ = run_fixture("reply_asks_captured")
    assert outcome.state.home_address.value == "4 High Street, Leeds LS1 1AA"
    assert "full name" not in outcome.reply
    assert outcome.reply == (
        "Thanks, I've noted that. Should this document cover all of your assets worldwide?"
    )
    assert WARN_REPLY_REPLACED in outcome.warnings


def test_wrong_type_passes_the_contract_but_fails_validation() -> None:
    before, outcome, _ = run_fixture("wrong_types")
    assert outcome.state == before
    assert outcome.rejected[0].reason == "'has_children' must be true or false"
    assert outcome.reply == "Do you have any children?"


def test_malformed_output_is_retried_with_a_repair_hint() -> None:
    _, outcome, provider = run_fixture("malformed_then_valid")
    assert outcome.state.full_name.value == "Jane Smith"
    assert outcome.warnings == (WARN_RETRIED,)
    first, second = provider.calls
    assert first.repair_hint is None
    assert second.repair_hint is not None
    assert second.repair_hint.startswith("invalid JSON")


@pytest.mark.parametrize("name", ["malformed_twice", "empty_response"])
def test_malformed_twice_leaves_state_unchanged_and_asks_again(name: str) -> None:
    before, outcome, provider = run_fixture(name)
    assert outcome.state == before
    assert outcome.changes == ()
    assert outcome.warnings == (WARN_RETRIED, WARN_FALLBACK)
    assert outcome.reply == "Sorry, I couldn't process that answer. What is your full name?"
    assert len(provider.calls) == 2


def test_refusal_leaves_state_unchanged() -> None:
    before = STATES["name_only"]
    outcome = handle_turn(ScriptedProvider([LLMRefused("no")]), before, [], "hello", turn=2)
    assert outcome.state == before
    assert outcome.warnings == (WARN_REFUSED,)
    assert outcome.reply == "Sorry, I couldn't process that answer. What is your home address?"


@pytest.mark.parametrize("error", [LLMUnavailable("timeout"), LLMNotConfigured("no key")])
def test_unavailable_or_unconfigured_model_raises_and_state_is_untouched(
    error: Exception,
) -> None:
    before = STATES["name_only"]
    snapshot = before.model_dump()
    with pytest.raises(type(error)):
        handle_turn(ScriptedProvider([error]), before, [], "hello", turn=2)
    assert before.model_dump() == snapshot


def test_model_receives_open_fields_in_order_and_recent_history() -> None:
    from app.llm.contracts import HistoryMessage

    history = [HistoryMessage("user", f"message {i}") for i in range(15)]
    provider = ScriptedProvider(['{"updates": [], "reply": "", "asks_about": null}'])
    handle_turn(provider, STATES["no_children"], history, "hi", turn=3)
    [ctx] = provider.calls
    assert ctx.remaining[:2] == ("home_address", "covers_worldwide_assets")
    assert "children_names" not in ctx.remaining
    assert len(ctx.history) == 10
    assert ctx.history[-1].content == "message 14"


def test_message_with_nothing_to_record_just_asks_the_question() -> None:
    provider = ScriptedProvider(['{"updates": [], "reply": "", "asks_about": null}'])
    outcome = handle_turn(provider, STATES["empty"], [], "hello there", turn=1)
    assert outcome.state == STATES["empty"]
    assert outcome.reply == "What is your full name?"


def test_opening_message_greets_and_asks_the_first_question() -> None:
    message = opening_message(WishesState.empty())
    assert "not legal advice" in message
    assert message.endswith("What is your full name?")
