"""Builds the configured `LLMProvider`. The only place that knows every implementation."""

from app.config import Settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.interface import LLMProvider
from app.llm.mock_provider import RuleBasedProvider


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        key = settings.anthropic_api_key
        # A missing key does not stop the server: calls raise LLMNotConfigured, which the API
        # reports clearly, and /api/health shows model_configured=false.
        return AnthropicProvider(
            api_key=key.get_secret_value().strip() if key else None,
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
            effort=settings.llm_effort,
        )
    return RuleBasedProvider()
