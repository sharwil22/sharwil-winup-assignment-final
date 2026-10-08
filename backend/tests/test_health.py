from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app


def health(settings: Settings) -> dict[str, object]:
    body: dict[str, object] = TestClient(create_app(settings)).get("/api/health").json()
    return body


def test_health_mock_provider_is_configured_without_key() -> None:
    body = health(Settings(llm_provider="mock", _env_file=None))
    assert body == {"status": "ok", "provider": "mock", "model_configured": True}


def test_health_anthropic_without_key_reports_not_configured() -> None:
    body = health(Settings(llm_provider="anthropic", anthropic_api_key=None, _env_file=None))
    assert body["provider"] == "anthropic"
    assert body["model_configured"] is False


def test_health_anthropic_with_key_reports_configured() -> None:
    settings = Settings(
        llm_provider="anthropic", anthropic_api_key=SecretStr("test-key"), _env_file=None
    )
    assert health(settings)["model_configured"] is True
