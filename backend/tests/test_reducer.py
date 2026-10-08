from app.domain.models import FieldStatus, Gift, WishesState
from app.domain.reducer import apply
from app.domain.updates import Certainty, UpdateKind
from tests.helpers import state_with, upd

EMPTY = WishesState.empty()
UNCLEAR = Certainty.UNCLEAR
CORRECTION = UpdateKind.CORRECTION


def test_several_updates_in_one_turn_are_all_captured() -> None:
    result = apply(
        EMPTY,
        [
            upd("has_children", False),
            upd("full_name", "Jane Smith"),
            upd("executor.relationship", "brother"),
            upd("executor.name", "James"),
        ],
        turn=3,
    )
    state = result.state
    assert state.full_name.value == "Jane Smith"
    assert state.full_name.status == FieldStatus.CAPTURED
    assert state.full_name.source_turn == 3
    assert state.executor.name.value == "James"
    assert state.executor.relationship.value == "brother"
    assert state.has_children.value is False
    assert state.version == 1
    assert result.conflicts == ()


def test_unclear_answer_waits_as_candidate_and_is_never_captured() -> None:
    state = apply(
        EMPTY, [upd("home_address", "London", "somewhere in London", certainty=UNCLEAR)], turn=1
    ).state
    field = state.home_address
    assert field.status == FieldStatus.NEEDS_CLARIFICATION
    assert field.value is None
    assert field.candidate == "London"
    assert field.note == 'Unclear answer: "somewhere in London"'


def test_explicit_answer_resolves_an_unclear_one() -> None:
    state = apply(EMPTY, [upd("home_address", "London", certainty=UNCLEAR)], turn=1).state
    state = apply(state, [upd("home_address", "4 High Street, London E1 1AA")], turn=2).state
    assert state.home_address.status == FieldStatus.CAPTURED
    assert state.home_address.value == "4 High Street, London E1 1AA"
    assert state.home_address.candidate is None
    assert state.home_address.note is None


def test_unclear_answer_on_captured_field_keeps_confirmed_value() -> None:
    state = state_with(upd("full_name", "Jane Smith"))
    state = apply(state, [upd("full_name", "Jan", certainty=UNCLEAR)], turn=2).state
    assert state.full_name.value == "Jane Smith"
    assert state.full_name.candidate == "Jan"
    assert state.full_name.status == FieldStatus.NEEDS_CLARIFICATION


def test_different_new_value_on_captured_field_is_a_conflict() -> None:
    state = state_with(upd("executor.name", "James"))
    result = apply(state, [upd("executor.name", "Anna")], turn=2)
    field = result.state.executor.name
    assert field.value == "James"  # confirmed value is kept
    assert field.candidate == "Anna"
    assert field.status == FieldStatus.NEEDS_CLARIFICATION
    assert [(c.path, c.current, c.proposed) for c in result.conflicts] == [
        ("executor.name", "James", "Anna")
    ]


def test_conflict_is_resolved_by_the_next_explicit_answer() -> None:
    state = state_with(upd("executor.name", "James"))
    state = apply(state, [upd("executor.name", "Anna")], turn=2).state
    state = apply(state, [upd("executor.name", "Anna")], turn=3).state
    assert state.executor.name.value == "Anna"
    assert state.executor.name.status == FieldStatus.CAPTURED
    assert state.executor.name.candidate is None


def test_correction_overwrites_and_is_recorded_as_a_change() -> None:
    state = state_with(upd("executor.name", "James"))
    result = apply(state, [upd("executor.name", "Anna", kind=CORRECTION)], turn=4)
    assert result.state.executor.name.value == "Anna"
    assert result.state.executor.name.status == FieldStatus.CAPTURED
    assert result.conflicts == ()
    [change] = result.changes
    assert (change.path, change.old_value, change.new_value, change.turn) == (
        "executor.name",
        "James",
        "Anna",
        4,
    )


def test_repeating_the_same_value_changes_nothing() -> None:
    state = state_with(upd("full_name", "Jane Smith"))
    result = apply(state, [upd("full_name", "  jane smith ")], turn=2)
    assert result.changes == ()
    assert result.conflicts == ()
    assert result.state == state
    assert result.state.version == state.version


def test_no_children_makes_children_names_not_applicable() -> None:
    state = apply(EMPTY, [upd("has_children", False)], turn=1).state
    assert state.children_names.status == FieldStatus.NOT_APPLICABLE


def test_switching_to_yes_reopens_children_names() -> None:
    state = state_with(upd("has_children", False))
    state = apply(state, [upd("has_children", True, kind=CORRECTION)], turn=2).state
    assert state.has_children.value is True
    assert state.children_names.status == FieldStatus.MISSING


def test_yes_and_names_in_one_turn_captures_both_whatever_the_order() -> None:
    updates = [upd("children_names", ["Tom", "Ann"]), upd("has_children", True)]
    state = apply(EMPTY, updates, turn=1).state
    assert state.has_children.value is True
    assert state.children_names.value == ["Tom", "Ann"]
    assert state.children_names.status == FieldStatus.CAPTURED


def test_names_without_has_children_answer_imply_yes() -> None:
    state = apply(EMPTY, [upd("children_names", ["Tom"])], turn=1).state
    assert state.has_children.value is True
    assert state.has_children.status == FieldStatus.CAPTURED
    assert state.has_children.note == "Implied by the children's names given"
    assert state.children_names.value == ["Tom"]


def test_contradiction_about_children_waits_for_clarification() -> None:
    # "No kids" earlier, then "leave the car to my son Tom".
    state = state_with(upd("has_children", False))
    result = apply(state, [upd("has_children", True), upd("children_names", ["Tom"])], turn=2)
    state = result.state
    assert state.has_children.value is False
    assert state.has_children.status == FieldStatus.NEEDS_CLARIFICATION
    assert state.children_names.status == FieldStatus.NEEDS_CLARIFICATION
    assert state.children_names.candidate == ["Tom"]
    assert [c.path for c in result.conflicts] == ["has_children"]


def test_resolving_children_conflict_with_no_clears_pending_names() -> None:
    state = state_with(upd("has_children", False))
    state = apply(state, [upd("has_children", True), upd("children_names", ["Tom"])], turn=2).state
    state = apply(state, [upd("has_children", False)], turn=3).state
    assert state.has_children.status == FieldStatus.CAPTURED
    assert state.children_names.status == FieldStatus.NOT_APPLICABLE
    assert state.children_names.candidate is None


def test_resolving_children_conflict_with_yes_keeps_names_to_confirm() -> None:
    state = state_with(upd("has_children", False))
    state = apply(state, [upd("has_children", True), upd("children_names", ["Tom"])], turn=2).state
    state = apply(state, [upd("has_children", True)], turn=3).state
    assert state.has_children.value is True
    assert state.children_names.status == FieldStatus.NEEDS_CLARIFICATION
    assert state.children_names.candidate == ["Tom"]


def test_none_answers_capture_optional_fields_as_empty() -> None:
    state = apply(EMPTY, [upd("specific_gifts", []), upd("additional_wishes", "")], turn=1).state
    assert state.specific_gifts.status == FieldStatus.CAPTURED
    assert state.specific_gifts.value == []
    assert state.additional_wishes.status == FieldStatus.CAPTURED
    assert state.additional_wishes.value == ""


def test_gifts_are_captured() -> None:
    gifts = [Gift(item="car", recipient="Tom")]
    state = apply(EMPTY, [upd("specific_gifts", gifts)], turn=1).state
    assert state.specific_gifts.value == gifts


def test_version_increments_once_per_turn_that_changes_something() -> None:
    state = apply(EMPTY, [upd("full_name", "Jane"), upd("home_address", "Leeds")], turn=1).state
    assert state.version == 1
    state = apply(state, [upd("full_name", "Jane")], turn=2).state
    assert state.version == 1
    state = apply(state, [upd("covers_worldwide_assets", True)], turn=3).state
    assert state.version == 2


def test_apply_never_mutates_the_input_state() -> None:
    before = state_with(upd("full_name", "Jane"))
    snapshot = before.model_dump()
    apply(before, [upd("full_name", "Anna", kind=CORRECTION)], turn=2)
    assert before.model_dump() == snapshot


def test_captured_values_record_where_they_came_from() -> None:
    state = apply(EMPTY, [upd("executor.name", "James", "my brother James")], turn=5).state
    field = state.executor.name
    assert (field.source, field.source_turn, field.evidence) == ("chat", 5, "my brother James")
    assert field.previous_value is None


def test_correction_keeps_the_replaced_value() -> None:
    state = state_with(upd("executor.name", "James", "brother James"))
    state = apply(state, [upd("executor.name", "Anna", "sister Anna", kind=CORRECTION)], 3).state
    assert state.executor.name.previous_value == "James"
    assert state.executor.name.evidence == "sister Anna"


def test_resolving_a_conflict_keeps_the_replaced_value() -> None:
    state = state_with(upd("executor.name", "James"))
    state = apply(state, [upd("executor.name", "Anna")], turn=2).state
    state = apply(state, [upd("executor.name", "Anna", "Anna")], turn=3).state
    assert state.executor.name.previous_value == "James"


def test_ui_edits_are_marked_as_edits_without_evidence() -> None:
    from app.domain.updates import ProposedUpdate, UpdateSource

    edit = ProposedUpdate(
        path="full_name", value="Jane Smith", kind=CORRECTION, source=UpdateSource.UI_EDIT
    )
    field = apply(EMPTY, [edit], turn=2).state.full_name
    assert (field.source, field.evidence) == ("edit", None)
