"""The live-eval harness itself (run here with the offline providers only)."""

import json

from app.domain.models import FieldStatus
from app.llm.mock_provider import RuleBasedProvider, ScriptedProvider
from scripts.eval import SCENARIOS, Check, main, run_scenario
from tests.helpers import state_with, upd


def test_checks_report_status_value_and_invention_problems() -> None:
    state = state_with(upd("full_name", "Jane Smith"))
    assert Check("full_name", FieldStatus.CAPTURED, equals="jane smith").run(state) is None
    assert Check("full_name", one_of=(None, "Jane")).run(state) == (
        "full_name: 'Jane Smith', expected one of (None, 'Jane')"
    )
    assert Check("home_address", FieldStatus.CAPTURED).run(state) == (
        "home_address: status missing, expected captured"
    )


def test_scenario_passes_with_a_correct_model() -> None:
    [scenario] = [s for s in SCENARIOS if s.name == "no_invention"]
    reply = json.dumps(
        {
            "updates": [
                {
                    "path": "full_name",
                    "value": "Jane",
                    "kind": "new",
                    "certainty": "explicit",
                    "evidence": "Jane",
                }
            ],
            "reply": "",
            "asks_about": None,
        }
    )
    assert run_scenario(ScriptedProvider([reply]), scenario).passed


def test_model_errors_are_reported_not_raised() -> None:
    from app.llm.contracts import LLMUnavailable

    result = run_scenario(ScriptedProvider([LLMUnavailable("timeout")]), SCENARIOS[0])
    assert not result.passed
    assert result.error == "timeout"


def test_demo_provider_run_completes_and_exits_zero() -> None:
    assert run_scenario(RuleBasedProvider(), SCENARIOS[0]).passed
    assert main(["--provider", "mock"]) == 0
