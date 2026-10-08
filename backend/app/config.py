"""Application settings loaded from environment variables and backend/.env."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: Literal["mock", "anthropic"] = "mock"
    anthropic_api_key: SecretStr | None = None
    llm_model: str = "claude-opus-5-5"
    # Low effort keeps chat turns fast; extraction is a short, well-specified task.
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    llm_timeout_s: float = 30.0

    @property
    def model_configured(self) -> bool:
        """True when the selected provider has everything it needs to run."""
        if self.llm_provider == "mock":
            return True
        key = self.anthropic_api_key
        return key is not None and key.get_secret_value().strip() != ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
