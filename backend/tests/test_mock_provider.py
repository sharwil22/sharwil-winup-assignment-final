"""The no-key demo provider, driven through the real pipeline end to end."""

from app.config import Settings
from app.domain.models import FieldStatus, Gift, WishesState
from app.domain.planner import COMPLETION_MESSAGE, is_complete
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.contracts import HistoryMessage
from app.llm.factory import build_provider
from app.llm.mock_provider import RuleBasedProvider
from app.services.interview import TurnOutcome, handle_turn


def converse(messages: list[str]) -> tuple[WishesState, list[TurnOutcome]]:
    provider = RuleBasedProvider()
    state = WishesState.empty()
    history: list[HistoryMessage] = []
    outcomes = []
    for turn, message in enumerate(messages, start=1):
        outcome = handle_turn(provider, state, history, message, turn)
        outcomes.append(outcome)
        state = outcome.state
        history += [HistoryMessage("user", message), HistoryMessage("assistant", outcome.reply)]
    return state, outcomes


def test_demo_conversation_reaches_a_complete_state() -> None:
    state, outcomes = converse(
        [
            "Hi, my name is Jane Smith",
            "4 High Street, Leeds LS1 1AA",
            "Yes",
            "No",
            "My brother James",
            "I'd like to leave my watch to James",
            "None",
        ]
    )
    assert is_complete(state)
    assert outcomes[-1].reply == COMPLETION_MESSAGE  # no "Thanks, I've noted that." before it
    plain = state.as_plain()
    assert plain["full_name"] == "Jane Smith"
    assert plain["home_address"] == "4 High Street, Leeds LS1 1AA"
    assert plain["covers_worldwide_assets"] is True
    assert plain["has_children"] is False
    assert plain["executor"] == {"name": "James", "relationship": "brother"}
    assert state.specific_gifts.value == [Gift(item="watch", recipient="James")]
    assert plain["additional_wishes"] == ""


def test_demo_handles_several_fields_at_once() -> None:
    state, _ = converse(["My name is Jane Smith, no kids, 4 High Street, Leeds LS1 1AA"])
    assert state.full_name.value == "Jane Smith"
    assert state.has_children.value is False
    assert state.home_address.value == "4 High Street, Leeds LS1 1AA"


def test_demo_holds_a_vague_address_for_clarification() -> None:
    state, outcomes = converse(["My name is Jane Smith", "Somewhere in London"])
    assert state.home_address.status == FieldStatus.NEEDS_CLARIFICATION
    assert outcomes[-1].reply == (
        "Could you give your full home address, including the street, town and postcode?"
    )  # no "Thanks, I've noted that.": nothing was recorded


def test_demo_applies_a_correction() -> None:
    state, _ = converse(
        [
            "My name is Jane Smith, no kids, 4 High Street, Leeds LS1 1AA",
            "Yes",
            "My brother James",
            "Actually, change my executor to my sister Anna",
        ]
    )
    assert state.as_plain()["executor"] == {"name": "Anna", "relationship": "sister"}


def test_factory_picks_provider_from_settings() -> None:
    mock = build_provider(Settings(llm_provider="mock", _env_file=None))
    real = build_provider(Settings(llm_provider="anthropic", _env_file=None))
    assert isinstance(mock, RuleBasedProvider)
    assert isinstance(real, AnthropicProvider)
