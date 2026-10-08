"""The one interface the application uses to talk to a model."""

from typing import Protocol

from app.llm.contracts import TurnContext, TurnExtraction


class LLMProvider(Protocol):
    name: str

    def extract(self, ctx: TurnContext) -> TurnExtraction:
        """Return the model's proposed updates and reply for one user turn.

        Raises `LLMMalformedOutput`, `LLMRefused`, `LLMUnavailable` or `LLMNotConfigured`.
        """
        ...
