"""Deterministic stand-ins for the model.

`ScriptedProvider` replays a queue of raw responses (fixtures) or errors. Tests use it to
drive valid, ambiguous and malformed model output through the real pipeline.

`RuleBasedProvider` is the default when no API key is configured. It is a small set of
regular expressions, not language understanding: it treats short answers as answers to the
current question and recognises a few multi-field phrasings, so a reviewer can walk through
the demo without a key. It still emits raw JSON that goes through `parse_extraction`, the
same path as the real model.
"""

import json
import re
from collections import deque
from collections.abc import Iterable
from typing import Any

from app.domain.models import BOOL_PATHS, FieldPath
from app.llm.contracts import TurnContext, TurnExtraction, parse_extraction


class ScriptedProvider:
    name = "scripted"

    def __init__(self, responses: Iterable[str | Exception]) -> None:
        self._queue: deque[str | Exception] = deque(responses)
        self.calls: list[TurnContext] = []

    def extract(self, ctx: TurnContext) -> TurnExtraction:
        self.calls.append(ctx)
        if not self._queue:
            raise AssertionError("ScriptedProvider has no more responses queued")
        item = self._queue.popleft()
        if isinstance(item, Exception):
            raise item
        return parse_extraction(item)


_YES = re.compile(r"^\s*(yes|yeah|yep|yup|correct|i do|it should|please do)\b", re.IGNORECASE)
_NO = re.compile(r"^\s*(no|nope|none|i don't|i do not|it shouldn't)\b", re.IGNORECASE)
_NONE = re.compile(r"^\s*(no|none|nothing|nope|no thanks|n/a)\b", re.IGNORECASE)
_HEDGE = re.compile(r"\b(maybe|not sure|i think|somewhere|probably|perhaps)\b", re.IGNORECASE)
_CORRECTION = re.compile(r"\b(actually|i meant|change|instead|correction)\b", re.IGNORECASE)
# Keywords match in any case; names must be capitalised, so (?i:...) is scoped to keywords.
_NAME = re.compile(r"\b(?i:my name is|i am|i'm|this is)\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)+)")
_RELATIVE = re.compile(
    r"\b(?i:my)\s+(?i:(brother|sister|wife|husband|partner|friend|son|daughter|mother|father|"
    r"mum|dad|cousin|uncle|aunt|niece|nephew|solicitor))\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)"
)
_NO_KIDS = re.compile(r"\b(no (kids|children)|don't have (any )?(kids|children))\b", re.IGNORECASE)
_GIFT = re.compile(
    r"\b(?i:leave)\s+(?i:my\s+|the\s+)?(.+?)\s+(?i:to)\s+(?i:my\s+\w+\s+)?"
    r"([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)"
)
_ADDRESS = re.compile(r"\b\d+[A-Za-z]?\s+[A-Z][\w'-]+.*,\s*.+")


class RuleBasedProvider:
    name = "mock"

    def extract(self, ctx: TurnContext) -> TurnExtraction:
        message = ctx.user_message.strip()
        focus = ctx.remaining[0] if ctx.remaining else None
        kind = "correction" if _CORRECTION.search(message) else "new"
        updates: dict[FieldPath, dict[str, Any]] = {}

        def add(path: FieldPath, value: Any, evidence: str, unclear: bool = False) -> None:
            updates.setdefault(
                path,
                {
                    "path": path,
                    "value": value,
                    "kind": kind,
                    "certainty": "unclear" if unclear else "explicit",
                    "evidence": evidence,
                },
            )

        # Phrasings recognised wherever they appear in the message.
        if match := _NAME.search(message):
            add("full_name", match.group(1), match.group(0))
        about_executor = (
            focus in ("executor.name", "executor.relationship") or "executor" in message.lower()
        )
        if about_executor and (match := _RELATIVE.search(message)):
            add("executor.name", match.group(2), match.group(0))
            add("executor.relationship", match.group(1), match.group(0))
        if match := _NO_KIDS.search(message):
            add("has_children", False, match.group(0))
        if match := _GIFT.search(message):
            add(
                "specific_gifts",
                [{"item": match.group(1), "recipient": match.group(2)}],
                match.group(0),
            )
        if match := _ADDRESS.search(message):
            add("home_address", match.group(0).rstrip(". "), match.group(0).rstrip(". "))

        # Otherwise, treat the message as an answer to the current question.
        if focus is not None and focus not in updates:
            self._answer_focus(focus, message, add)

        payload = {"updates": list(updates.values()), "reply": "", "asks_about": None}
        return parse_extraction(json.dumps(payload))

    @staticmethod
    def _answer_focus(focus: FieldPath, message: str, add: Any) -> None:
        unclear = bool(_HEDGE.search(message))
        if focus in BOOL_PATHS:
            if match := _YES.search(message):
                add(focus, True, match.group(0), unclear)
            elif match := _NO.search(message):
                add(focus, False, match.group(0), unclear)
        elif focus in ("specific_gifts", "additional_wishes") and (match := _NONE.search(message)):
            add(focus, [] if focus == "specific_gifts" else "", match.group(0))
        elif focus == "children_names":
            names = [n.strip(" .") for n in re.split(r",|\band\b", message) if n.strip(" .")]
            if names:
                add(focus, names, message, unclear)
        elif focus == "home_address":
            add(focus, message.rstrip("."), message, unclear or not _ADDRESS.search(message))
        elif focus != "specific_gifts" and message:
            add(focus, message.rstrip("."), message, unclear)
