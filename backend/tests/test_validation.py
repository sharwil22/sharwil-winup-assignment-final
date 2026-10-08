import pytest

from app.domain.models import WishesState
from app.domain.updates import ProposedUpdate, UpdateSource
from app.domain.validation import validate_updates
from tests.helpers import state_with, upd

EMPTY = WishesState.empty()


def reasons(updates: list[ProposedUpdate], message: str, state: WishesState = EMPTY) -> list[str]:
    return [r.reason for r in validate_updates(updates, state, message).rejected]


def test_valid_multi_field_message_is_accepted_and_normalised() -> None:
    message = "I'm Jane   Smith, I live at 4 High Street, Leeds. No children."
    result = validate_updates(
        [
            upd("full_name", "  Jane   Smith ", "Jane Smith"),
            upd("home_address", "4 High Street, Leeds", "4 High Street, Leeds"),
            upd("has_children", False, "no children"),
        ],
        EMPTY,
        message,
    )
    assert result.rejected == ()
    assert [u.value for u in result.accepted] == ["Jane Smith", "4 High Street, Leeds", False]


def test_evidence_must_appear_in_the_users_message() -> None:
    assert reasons([upd("full_name", "Jane Smith", "Jane Smith")], "My name is Jane") == [
        "evidence does not appear in the user's message"
    ]


def test_evidence_is_required_for_chat_updates() -> None:
    assert reasons([upd("full_name", "Jane", "")], "Jane") == [
        "no evidence quoted from the user's message"
    ]


def test_evidence_match_ignores_case_whitespace_and_edge_punctuation() -> None:
    assert (
        reasons([upd("executor.name", "James", '"my BROTHER  james."')], "My brother James") == []
    )


def test_ui_edits_do_not_need_evidence() -> None:
    edit = ProposedUpdate(path="full_name", value="Jane Smith", source=UpdateSource.UI_EDIT)
    assert reasons([edit], "") == []


@pytest.mark.parametrize(
    ("path", "value", "reason"),
    [
        ("has_children", "maybe", "'has_children' must be true or false"),
        ("covers_worldwide_assets", "yes", "'covers_worldwide_assets' must be true or false"),
        ("full_name", True, "'full_name' must be text"),
        ("full_name", "   ", "'full_name' must not be empty"),
        ("children_names", [], "'children_names' must be a non-empty list of names"),
        ("children_names", ["Tom", " "], "'children_names' must contain only non-empty names"),
        ("specific_gifts", "my car", "'specific_gifts' must be a list of {item, recipient}"),
        (
            "specific_gifts",
            [{"item": "car", "recipient": " "}],
            "each gift needs both an item and a recipient",
        ),
    ],
)
def test_wrong_types_and_empty_values_are_rejected(path: str, value: object, reason: str) -> None:
    update = ProposedUpdate.model_validate({"path": path, "value": value, "evidence": "x"})
    assert reasons([update], "x") == [reason]


def test_optional_fields_accept_none_answers() -> None:
    message = "no gifts and nothing else"
    assert reasons([upd("specific_gifts", [], "no gifts")], message) == []
    assert reasons([upd("additional_wishes", "", "nothing else")], message) == []


def test_children_names_rejected_when_user_said_no_children() -> None:
    state = state_with(upd("has_children", False))
    assert reasons([upd("children_names", ["Tom"], "my son Tom")], "my son Tom", state) == [
        "children's names given while 'has_children' is no"
    ]


def test_children_names_allowed_when_same_turn_says_yes() -> None:
    state = state_with(upd("has_children", False))
    message = "actually I do have children, my son Tom"
    updates = [
        upd("children_names", ["Tom"], "my son Tom"),
        upd("has_children", True, "I do have children"),
    ]
    assert reasons(updates, message, state) == []


def test_second_update_for_same_path_in_one_turn_is_rejected() -> None:
    message = "James, or maybe Anna"
    result = validate_updates(
        [upd("executor.name", "James", "James"), upd("executor.name", "Anna", "Anna")],
        EMPTY,
        message,
    )
    assert [u.value for u in result.accepted] == ["James"]
    assert [r.reason for r in result.rejected] == [
        "duplicate update for 'executor.name' in one turn"
    ]


def test_unknown_path_fails_shape_validation() -> None:
    with pytest.raises(ValueError):
        ProposedUpdate.model_validate({"path": "favourite_colour", "value": "blue"})
