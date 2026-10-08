"""Live evaluation: scripted conversations against the configured model.

Unit tests prove the pipeline handles recorded model output correctly. This script checks
the other half: does the *real* model produce the right updates for realistic messages?
Each scenario runs a short conversation through `handle_turn` (the same code the API uses)
and checks the final state.

    make eval                               # uses backend/.env (LLM_PROVIDER, ANTHROPIC_API_KEY)
    uv run python -m scripts.eval --provider mock     # the regex demo, for comparison

Costs a few cents per run with a real model. Not part of `make test` / CI.
"""

import argparse
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.documents.generator import render
from app.domain.models import FieldPath, FieldStatus, WishesState
from app.domain.planner import is_complete
from app.domain.values import comparable_text
from app.llm.contracts import HistoryMessage, LLMError
from app.llm.factory import build_provider
from app.llm.interface import LLMProvider
from app.services.interview import WARN_FALLBACK, WARN_REPLY_REPLACED, handle_turn


@dataclass(frozen=True)
class Check:
    path: FieldPath
    status: FieldStatus | None = None
    equals: Any = None  # compared case-insensitively for text
    contains: str | None = None
    one_of: tuple[Any, ...] | None = None  # e.g. (None, "Jane"): anything else is invented

    def run(self, state: WishesState) -> str | None:
        field_ = state.get(self.path)
        if self.status is not None and field_.status != self.status:
            return f"{self.path}: status {field_.status.value}, expected {self.status.value}"
        value = field_.value
        if self.equals is not None and not _same(value, self.equals):
            return f"{self.path}: {value!r}, expected {self.equals!r}"
        if self.contains is not None and (
            not isinstance(value, str) or self.contains.casefold() not in value.casefold()
        ):
            return f"{self.path}: {value!r} does not contain {self.contains!r}"
        if self.one_of is not None and not any(_same(value, v) for v in self.one_of):
            return f"{self.path}: {value!r}, expected one of {self.one_of!r}"
        return None


@dataclass(frozen=True)
class Scenario:
    name: str
    what_it_tests: str
    messages: tuple[str, ...]
    checks: tuple[Check, ...] = field(default_factory=tuple)
    complete: bool | None = None  # interview finished (no open fields) at the end
    document_contains: tuple[str, ...] = ()  # phrases the final draft must contain


_ADDRESS = "4 High Street, Leeds LS1 1AA"
_TO_EXECUTOR = ("Jane Smith", _ADDRESS, "Yes", "No")

SCENARIOS = (
    Scenario(
        "multi_field",
        "several fields in one message, any order",
        (f"I'm Jane Smith, no kids, and I live at {_ADDRESS}.",),
        (
            Check("full_name", FieldStatus.CAPTURED, equals="Jane Smith"),
            Check("home_address", FieldStatus.CAPTURED, contains="4 High Street"),
            Check("has_children", FieldStatus.CAPTURED, equals=False),
            Check("children_names", FieldStatus.NOT_APPLICABLE),
        ),
    ),
    Scenario(
        "executor_relationship",
        '"My brother James" gives name and relationship',
        (*_TO_EXECUTOR, "My brother James."),
        (
            Check("executor.name", FieldStatus.CAPTURED, equals="James"),
            Check("executor.relationship", FieldStatus.CAPTURED, equals="brother"),
        ),
    ),
    Scenario(
        "correction",
        "an explicit change overwrites the earlier answer",
        (*_TO_EXECUTOR, "My brother James.", "Actually, make my sister Anna the executor instead."),
        (
            Check("executor.name", FieldStatus.CAPTURED, equals="Anna"),
            Check("executor.relationship", FieldStatus.CAPTURED, equals="sister"),
        ),
    ),
    Scenario(
        "contradiction",
        "a later answer that disagrees is flagged, not silently applied",
        (*_TO_EXECUTOR, "My brother James.", "I want to leave my car to my son Tom."),
        (Check("has_children", FieldStatus.NEEDS_CLARIFICATION, equals=False),),
    ),
    Scenario(
        "vague_address",
        "a partial address is held for clarification",
        ("Jane Smith", "Somewhere in London."),
        (Check("home_address", FieldStatus.NEEDS_CLARIFICATION),),
    ),
    Scenario(
        "no_invention",
        "no surname is invented",
        ("Just call me Jane.",),
        (Check("full_name", one_of=(None, "Jane")),),
    ),
    Scenario(
        "any_order",
        "answers given before they are asked for are captured",
        (
            "Before anything else: I want my sister Anna as executor, and no kids.",
            "Jane Smith",
        ),
        (
            Check("full_name", FieldStatus.CAPTURED, equals="Jane Smith"),
            Check("executor.name", FieldStatus.CAPTURED, equals="Anna"),
            Check("executor.relationship", FieldStatus.CAPTURED, equals="sister"),
            Check("has_children", FieldStatus.CAPTURED, equals=False),
        ),
    ),
    Scenario(
        "full_interview",
        "a natural interview reaches a complete, labelled draft",
        (
            "Hello, I'm Jane Smith.",
            _ADDRESS,
            "Yes, everything worldwide.",
            "Yes, two: Tom and Ann.",
            "My brother James.",
            "I'd like Tom to have my piano.",
            "No, nothing else.",
        ),
        (
            Check("children_names", FieldStatus.CAPTURED, equals=["Tom", "Ann"]),
            Check("specific_gifts", FieldStatus.CAPTURED),
            Check("additional_wishes", FieldStatus.CAPTURED, equals=""),
        ),
        complete=True,
        document_contains=(
            "FICTIONAL DRAFT — NOT LEGAL ADVICE",
            "I have the following children: Tom and Ann.",
            "I appoint James, my brother, as executor",
            "Draft status: all sections complete",
        ),
    ),
)


@dataclass
class Result:
    scenario: Scenario
    failures: list[str]
    replies_replaced: int
    fallbacks: int
    seconds: float
    error: str | None = None

    @property
    def passed(self) -> bool:
        return not self.failures and self.error is None


def run_scenario(provider: LLMProvider, scenario: Scenario) -> Result:
    state = WishesState.empty()
    history: list[HistoryMessage] = []
    replaced = fallbacks = 0
    reasked: list[str] = []
    started = time.monotonic()
    try:
        for turn, message in enumerate(scenario.messages, start=1):
            before = state
            outcome = handle_turn(provider, state, history, message, turn)
            replaced += WARN_REPLY_REPLACED in outcome.warnings
            fallbacks += WARN_FALLBACK in outcome.warnings
            state = outcome.state
            history += [HistoryMessage("user", message), HistoryMessage("assistant", outcome.reply)]
            # The brief: never ask again for something already captured (unless it's in conflict).
            focus = outcome.focus
            if (
                focus is not None
                and before.get(focus).status == FieldStatus.CAPTURED
                and state.get(focus).status == FieldStatus.CAPTURED
            ):
                reasked.append(f"turn {turn} asked again about captured field {focus}")
    except LLMError as exc:
        return Result(scenario, [], replaced, fallbacks, time.monotonic() - started, str(exc))
    failures = [problem for check in scenario.checks if (problem := check.run(state))]
    failures += reasked
    if scenario.complete is not None and is_complete(state) != scenario.complete:
        failures.append(f"interview complete={is_complete(state)}, expected {scenario.complete}")
    document = render(state)
    failures += [
        f"draft is missing {phrase!r}"
        for phrase in scenario.document_contains
        if phrase not in document
    ]
    return Result(scenario, failures, replaced, fallbacks, time.monotonic() - started)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provider", choices=["mock", "anthropic"], help="override LLM_PROVIDER")
    parser.add_argument("--only", help="run one scenario by name")
    parser.add_argument(
        "--repeat", type=int, default=1, help="run each scenario N times (models vary run to run)"
    )
    args = parser.parse_args(argv)

    settings = Settings()
    if args.provider:
        settings = settings.model_copy(update={"llm_provider": args.provider})
    if settings.llm_provider == "anthropic" and not settings.model_configured:
        print("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set (backend/.env).")
        return 2
    provider = build_provider(settings)
    label = settings.llm_model if settings.llm_provider == "anthropic" else "mock (regex demo)"
    print(f"Provider: {label}\n")

    scenarios = [s for s in SCENARIOS if not args.only or s.name == args.only]
    runs = max(1, args.repeat)
    width = max(len(s.name) for s in scenarios)
    all_passed = 0
    for scenario in scenarios:
        results = [run_scenario(provider, scenario) for _ in range(runs)]
        ok = sum(r.passed for r in results)
        all_passed += ok == runs
        mark = "PASS" if ok == runs else "FAIL"
        rate = f"  {ok}/{runs} runs" if runs > 1 else ""
        seconds = sum(r.seconds for r in results) / runs
        replaced = sum(r.replies_replaced for r in results)
        extra = f"  replies replaced: {replaced}" if replaced else ""
        fallbacks = sum(r.fallbacks for r in results)
        extra += f"  fallbacks: {fallbacks}" if fallbacks else ""
        name = f"{scenario.name:<{width}}"
        print(f"{mark}  {name}  {seconds:5.1f}s{rate}  {scenario.what_it_tests}{extra}")
        for problem in sorted({p for r in results for p in r.failures}):
            print(f"        - {problem}")
        for error in sorted({r.error for r in results if r.error}):
            print(f"        - error: {error}")

    print(
        f"\n{all_passed}/{len(scenarios)} scenarios passed"
        + (f" on all {runs} runs" if runs > 1 else "")
    )
    if settings.llm_provider == "mock":
        print("(The regex demo is expected to miss scenarios that need language understanding.)")
        return 0
    return 0 if all_passed == len(scenarios) else 1


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return comparable_text(a) == comparable_text(b)
    return bool(a == b)


if __name__ == "__main__":
    sys.exit(main())
