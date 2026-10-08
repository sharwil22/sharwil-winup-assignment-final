"""Claude adapter for `LLMProvider`.

- Structured outputs (`output_config.format` with the `TurnExtraction` JSON schema) make
  the response JSON-shaped by construction; we still parse it through the same Pydantic
  contract, because a truncated or refused response may not match.
- Forced tool use is not used: current Claude models reject `tool_choice` any/tool.
- `fallbacks: "default"` lets the API re-run a safety-declined request on a recommended
  fallback model server-side (beta). A refusal that survives it raises `LLMRefused`.
- SDK errors are mapped onto our own small error hierarchy, so nothing above `app.llm`
  depends on the vendor SDK.
"""

import logging
from typing import Literal

import anthropic

from app.llm.contracts import (
    EXTRACTION_SCHEMA,
    LLMMalformedOutput,
    LLMNotConfigured,
    LLMRefused,
    LLMUnavailable,
    TurnContext,
    TurnExtraction,
    parse_extraction,
)
from app.llm.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_content

logger = logging.getLogger(__name__)

Effort = Literal["low", "medium", "high", "xhigh", "max"]

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 8000  # thinking + JSON; well under the non-streaming timeout


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        api_key: str | None,
        model: str,
        timeout_s: float,
        effort: Effort = "low",
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._model = model
        self._effort: Effort = effort
        if client is not None:
            self._client: anthropic.Anthropic | None = client
        elif api_key:
            # One SDK retry for transient errors; the turn as a whole must stay responsive.
            self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_s, max_retries=1)
        else:
            self._client = None

    def extract(self, ctx: TurnContext) -> TurnExtraction:
        if self._client is None:
            raise LLMNotConfigured("ANTHROPIC_API_KEY is not set")

        try:
            response = self._client.beta.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_content(ctx)}],
                output_config={
                    "effort": self._effort,
                    "format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA},
                },
            )
        except anthropic.AuthenticationError as exc:
            raise LLMNotConfigured("the API key was rejected") from exc
        except anthropic.PermissionDeniedError as exc:
            raise LLMNotConfigured("the API key lacks permission for this model") from exc
        except anthropic.NotFoundError as exc:
            raise LLMNotConfigured(f"model '{self._model}' was not found") from exc
        except anthropic.BadRequestError as exc:
            raise LLMUnavailable(f"the model rejected the request: {exc.message}") from exc
        except anthropic.APITimeoutError as exc:
            raise LLMUnavailable("the model timed out") from exc
        except anthropic.RateLimitError as exc:
            raise LLMUnavailable("the model is rate limited") from exc
        except anthropic.APIStatusError as exc:
            raise LLMUnavailable(f"model service error ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMUnavailable("could not reach the model service") from exc

        logger.info(
            "llm_call model=%s prompt=%s stop=%s in=%s out=%s",
            response.model,
            PROMPT_VERSION,
            response.stop_reason,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        if response.stop_reason == "refusal":
            raise LLMRefused("the model declined to answer")
        if response.stop_reason == "max_tokens":
            raise LLMMalformedOutput("the response was cut off (max_tokens)")

        text = next((block.text for block in response.content if block.type == "text"), None)
        return parse_extraction(text)
