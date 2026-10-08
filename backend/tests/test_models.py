from app.domain.models import FIELD_PATHS, Field, FieldStatus, Gift, WishesState


def test_empty_state_has_every_field_missing() -> None:
    state = WishesState.empty()
    assert len(FIELD_PATHS) == 9
    assert all(state.get(path).status == FieldStatus.MISSING for path in FIELD_PATHS)
    assert state.version == 0


def test_as_plain_of_empty_state_is_all_none() -> None:
    assert WishesState.empty().as_plain() == {
        "full_name": None,
        "home_address": None,
        "covers_worldwide_assets": None,
        "has_children": None,
        "children_names": None,
        "executor": {"name": None, "relationship": None},
        "specific_gifts": None,
        "additional_wishes": None,
    }


def test_with_field_returns_new_state_and_leaves_original_untouched() -> None:
    original = WishesState.empty()
    updated = original.with_field(
        "executor.name", Field[str](value="James Smith", status=FieldStatus.CAPTURED)
    )
    assert original.executor.name.value is None
    assert updated.executor.name.value == "James Smith"
    assert updated.as_plain()["executor"] == {"name": "James Smith", "relationship": None}


def test_as_plain_shows_only_confirmed_values_not_candidates() -> None:
    state = WishesState.empty().with_field(
        "home_address",
        Field[str](status=FieldStatus.NEEDS_CLARIFICATION, candidate="somewhere in London"),
    )
    assert state.as_plain()["home_address"] is None


def test_as_plain_serialises_gifts() -> None:
    state = WishesState.empty().with_field(
        "specific_gifts",
        Field[list[Gift]](value=[Gift(item="car", recipient="Tom")], status=FieldStatus.CAPTURED),
    )
    assert state.as_plain()["specific_gifts"] == [{"item": "car", "recipient": "Tom"}]


def test_state_round_trips_through_json() -> None:
    state = WishesState.empty().with_field(
        "has_children", Field[bool](value=False, status=FieldStatus.CAPTURED)
    )
    assert WishesState.model_validate_json(state.model_dump_json()) == state
