"""The Claude adapter, tested against a fake SDK client (no network)."""

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from app.domain.models import WishesState
from app.llm.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from app.llm.contracts import (
    EXTRACTION_SCHEMA,
    LLMMalformedOutput,
    LLMNotConfigured,
    LLMRefused,
    LLMUnavailable,
    TurnContext,
)
from app.llm.prompts import SYSTEM_PROMPT

CTX = TurnContext(WishesState.empty(), ("full_name",), (), "My name is Jane Smith.")
VALID_JSON = json.dumps(
    {
        "updates": [
            {
                "path": "full_name",
                "value": "Jane Smith",
                "kind": "new",
                "certainty": "explicit",
                "evidence": "Jane Smith",
            }
        ],
        "reply": "Thanks!",
        "asks_about": "home_address",
    }
)
_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def response(text: str | None, stop_reason: str = "end_turn") -> SimpleNamespace:
    content = [] if text is None else [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(
        model="claude-opus-5-5",
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="thinking", thinking=""), *content],
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
    )


class FakeClient:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.kwargs: dict[str, Any] = {}
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def provider_with(result: Any) -> tuple[AnthropicProvider, FakeClient]:
    client = FakeClient(result)
    provider = AnthropicProvider(
        api_key=None,
        model="claude-opus-5-5",
        timeout_s=5,
        effort="low",
        client=client,  # type: ignore[arg-type]
    )
    return provider, client


def test_valid_response_is_parsed() -> None:
    provider, _ = provider_with(response(VALID_JSON))
    assert provider.extract(CTX).updates[0].value == "Jane Smith"


def test_request_uses_structured_outputs_fallbacks_and_fenced_message() -> None:
    provider, client = provider_with(response(VALID_JSON))
    provider.extract(CTX)
    kwargs = client.kwargs
    assert kwargs["model"] == "claude-opus-5-5"
    assert kwargs["system"] == SYSTEM_PROMPT
    assert kwargs["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA},
    }
    assert kwargs["betas"] == [FALLBACK_BETA]
    assert kwargs["fallbacks"] == "default"
    assert "tool_choice" not in kwargs
    [message] = kwargs["messages"]
    assert "<user_message>\nMy name is Jane Smith.\n</user_message>" in message["content"]


def test_missing_api_key_raises_not_configured() -> None:
    provider = AnthropicProvider(api_key=None, model="claude-opus-5-5", timeout_s=5)
    with pytest.raises(LLMNotConfigured):
        provider.extract(CTX)


def test_refusal_raises_refused() -> None:
    provider, _ = provider_with(response(None, stop_reason="refusal"))
    with pytest.raises(LLMRefused):
        provider.extract(CTX)


def test_truncated_response_is_malformed() -> None:
    provider, _ = provider_with(response('{"updates": [', stop_reason="max_tokens"))
    with pytest.raises(LLMMalformedOutput, match="cut off"):
        provider.extract(CTX)


def test_response_without_text_is_malformed() -> None:
    provider, _ = provider_with(response(None))
    with pytest.raises(LLMMalformedOutput, match="empty response"):
        provider.extract(CTX)


def _status_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    return cls("error", response=httpx2.Response(status, request=_REQUEST), body=None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_status_error(anthropic.AuthenticationError, 401), LLMNotConfigured),
        (_status_error(anthropic.PermissionDeniedError, 403), LLMNotConfigured),
        (_status_error(anthropic.NotFoundError, 404), LLMNotConfigured),
        (_status_error(anthropic.RateLimitError, 429), LLMUnavailable),
        (_status_error(anthropic.InternalServerError, 500), LLMUnavailable),
        (anthropic.APITimeoutError(request=_REQUEST), LLMUnavailable),
        (anthropic.APIConnectionError(request=_REQUEST), LLMUnavailable),
    ],
)
def test_sdk_errors_map_to_application_errors(error: Exception, expected: type[Exception]) -> None:
    provider, _ = provider_with(error)
    with pytest.raises(expected):
        provider.extract(CTX)
