from app.domain.models import FIELD_PATHS, WishesState
from app.domain.planner import (
    COMPLETION_MESSAGE,
    is_complete,
    next_focus,
    next_question,
    progress,
    question_for,
)
from app.domain.reducer import apply
from app.domain.updates import Certainty
from tests.helpers import state_with, upd

COMPLETE = state_with(
    upd("full_name", "Jane Smith"),
    upd("home_address", "4 High Street, Leeds"),
    upd("covers_worldwide_assets", True),
    upd("has_children", False),
    upd("executor.name", "James Smith"),
    upd("executor.relationship", "brother"),
    upd("specific_gifts", []),
    upd("additional_wishes", ""),
)


def test_empty_state_starts_with_full_name() -> None:
    state = WishesState.empty()
    assert next_focus(state) == "full_name"
    assert next_question(state) == "What is your full name?"


def test_captured_fields_are_skipped_in_interview_order() -> None:
    state = state_with(upd("full_name", "Jane"), upd("covers_worldwide_assets", True))
    assert next_focus(state) == "home_address"


def test_captured_fields_are_never_asked_again() -> None:
    state = WishesState.empty()
    asked: list[str] = []
    for path in FIELD_PATHS:
        focus = next_focus(state)
        assert focus is not None
        assert focus not in asked
        asked.append(focus)
        value: object = {"covers_worldwide_assets": True, "has_children": True}.get(path, "x")
        if path == "children_names":
            value = ["Tom"]
        elif path == "specific_gifts":
            value = []
        state = apply(state, [upd(focus, value)], turn=len(asked)).state
    assert next_focus(state) is None


def test_not_applicable_children_names_are_skipped() -> None:
    state = state_with(
        upd("full_name", "Jane"),
        upd("home_address", "Leeds"),
        upd("covers_worldwide_assets", False),
        upd("has_children", False),
    )
    assert next_focus(state) == "executor.name"


def test_clarification_comes_before_missing_fields() -> None:
    state = state_with(upd("full_name", "Jane"))
    state = apply(state, [upd("executor.name", "James", certainty=Certainty.UNCLEAR)], turn=2).state
    assert next_focus(state) == "executor.name"


def test_conflict_question_names_both_answers() -> None:
    state = state_with(upd("executor.name", "James"))
    state = apply(state, [upd("executor.name", "Anna")], turn=2).state
    assert question_for("executor.name", state) == (
        'Earlier you gave "James" for executor\'s name, but now "Anna". Which is correct?'
    )


def test_children_conflict_question_reads_naturally() -> None:
    state = state_with(upd("has_children", False))
    state = apply(state, [upd("has_children", True), upd("children_names", ["Tom"])], turn=2).state
    assert next_focus(state) == "has_children"
    assert next_question(state) == (
        'Earlier you gave "no" for whether you have children, but now "yes". Which is correct?'
    )


def test_vague_address_asks_for_the_full_address() -> None:
    state = apply(
        WishesState.empty(),
        [upd("home_address", "London", certainty=Certainty.UNCLEAR)],
        turn=1,
    ).state
    assert next_question(state) == (
        "Could you give your full home address, including the street, town and postcode?"
    )


def test_unclear_yes_no_answer_asks_for_yes_or_no() -> None:
    state = apply(
        WishesState.empty(),
        [upd("covers_worldwide_assets", True, certainty=Certainty.UNCLEAR)],
        turn=1,
    ).state
    assert next_question(state).endswith("Please answer yes or no.")


def test_executor_relationship_question_uses_the_executors_name() -> None:
    state = state_with(upd("executor.name", "James"))
    assert question_for("executor.relationship", state) == "What is James's relationship to you?"


def test_progress_counts_captured_and_not_applicable() -> None:
    assert progress(WishesState.empty()).completed == 0
    assert progress(state_with(upd("has_children", False))).completed == 2
    assert progress(COMPLETE).completed == progress(COMPLETE).total == 9


def test_complete_state_has_no_focus_and_a_completion_message() -> None:
    assert is_complete(COMPLETE)
    assert next_focus(COMPLETE) is None
    assert next_question(COMPLETE) == COMPLETION_MESSAGE
