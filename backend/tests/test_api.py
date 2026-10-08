"""The HTTP contract, end to end through FastAPI with no network."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.documents.generator import DISCLAIMER
from app.llm.contracts import LLMNotConfigured, LLMUnavailable, TurnContext, TurnExtraction
from app.llm.mock_provider import RuleBasedProvider, ScriptedProvider
from app.main import create_app

SETTINGS = Settings(llm_provider="mock", _env_file=None)


def client_with(provider: Any = None) -> TestClient:
    app = create_app(SETTINGS, provider=provider or RuleBasedProvider())
    return TestClient(app, raise_server_exceptions=False)


def start(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/sessions")
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


def say(client: TestClient, session: dict[str, Any], content: str) -> dict[str, Any]:
    response = client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": content, "expected_version": session["version"]},
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def error_of(response: Any) -> dict[str, Any]:
    error: dict[str, Any] = response.json()["error"]
    return error


def test_new_session_has_opening_question_empty_state_and_draft() -> None:
    session = start(client_with())
    assert session["version"] == 0
    assert session["messages"] == [
        {"role": "assistant", "content": session["messages"][0]["content"]}
    ]
    assert session["messages"][0]["content"].endswith("What is your full name?")
    assert session["focus"] == "full_name"
    assert session["progress"] == {"completed": 0, "total": 9}
    assert session["is_complete"] is False
    assert all(f["status"] == "missing" for f in session["fields"])
    assert session["state"]["full_name"] is None
    assert DISCLAIMER in session["document_markdown"]


def test_full_conversation_through_the_api() -> None:
    client = client_with()
    session = start(client)
    for message in [
        "My name is Jane Smith, no kids, 4 High Street, Leeds LS1 1AA",
        "Yes",
        "My brother James",
        "I'd like to leave my watch to James",
        "None",
    ]:
        session = say(client, session, message)

    assert session["is_complete"] is True
    assert session["version"] == 5
    assert session["state"]["executor"] == {"name": "James", "relationship": "brother"}
    assert session["state"]["specific_gifts"] == [{"item": "watch", "recipient": "James"}]
    assert "To be confirmed" not in session["document_markdown"]
    assert len(session["messages"]) == 11  # opening + 5 user/assistant pairs

    fetched = client.get(f"/api/sessions/{session['id']}").json()
    assert fetched["state"] == session["state"]
    assert fetched["version"] == session["version"]


def test_turn_result_reports_changes_reply_and_warnings() -> None:
    client = client_with()
    result = say(client, start(client), "My name is Jane Smith")
    assert result["reply"] == "Thanks, I've noted that. What is your home address?"
    assert result["changes"] == [
        {
            "path": "full_name",
            "label": "full name",
            "old_value": None,
            "new_value": "Jane Smith",
            "old_status": "missing",
            "new_status": "captured",
        }
    ]
    assert result["rejected_updates"] == []
    assert result["warnings"] == []
    assert result["messages"][-1] == {"role": "assistant", "content": result["reply"]}


def test_rejected_updates_are_reported() -> None:
    invented = json.dumps(
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
            "reply": "Thanks Jane Smith!",
            "asks_about": "home_address",
        }
    )
    client = client_with(ScriptedProvider([invented]))
    result = say(client, start(client), "Call me Jane")
    assert result["state"]["full_name"] is None
    assert result["rejected_updates"] == [
        {"path": "full_name", "reason": "evidence does not appear in the user's message"}
    ]
    assert "updates_rejected" in result["warnings"]


def test_stale_version_is_rejected_with_409_and_no_model_call() -> None:
    provider = ScriptedProvider([])  # any model call would raise
    client = client_with(provider)
    session = start(client)
    response = client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hello", "expected_version": 7},
    )
    assert response.status_code == 409
    assert error_of(response) == {
        "code": "version_conflict",
        "message": "This session changed in another request. Reload it and try again.",
        "retryable": True,
    }
    assert provider.calls == []


def test_concurrent_save_loses_with_409() -> None:
    """Two requests start from the same version; only the first one is saved."""
    client = client_with()
    session = start(client)
    say(client, session, "My name is Jane Smith")  # version 0 -> 1
    response = client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "4 High Street, Leeds LS1 1AA", "expected_version": 0},
    )
    assert response.status_code == 409


def test_unknown_session_is_404() -> None:
    client = client_with()
    for response in (
        client.get("/api/sessions/nope"),
        client.post("/api/sessions/nope/messages", json={"content": "hi", "expected_version": 0}),
        client.get("/api/sessions/nope/document"),
    ):
        assert response.status_code == 404
        assert error_of(response)["code"] == "session_not_found"


@pytest.mark.parametrize(
    "body",
    [
        {"content": "", "expected_version": 0},
        {"content": "   ", "expected_version": 0},
        {"content": "x" * 2001, "expected_version": 0},
        {"content": "hi"},
        {"content": "hi", "expected_version": 0, "extra": True},
    ],
)
def test_invalid_message_bodies_are_422(body: dict[str, Any]) -> None:
    client = client_with()
    session = start(client)
    response = client.post(f"/api/sessions/{session['id']}/messages", json=body)
    assert response.status_code == 422
    assert error_of(response)["code"] == "validation_error"


@pytest.mark.parametrize(
    ("error", "code", "retryable"),
    [
        (LLMUnavailable("timeout"), "llm_unavailable", True),
        (LLMNotConfigured("ANTHROPIC_API_KEY is not set"), "llm_not_configured", False),
    ],
)
def test_model_failures_are_503_and_leave_the_session_unchanged(
    error: Exception, code: str, retryable: bool
) -> None:
    client = client_with(ScriptedProvider([error]))
    session = start(client)
    response = client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "My name is Jane", "expected_version": 0},
    )
    assert response.status_code == 503
    assert error_of(response)["code"] == code
    assert error_of(response)["retryable"] is retryable

    after = client.get(f"/api/sessions/{session['id']}").json()
    assert after == session  # nothing saved, not even the user's message


def test_missing_key_gives_a_helpful_message() -> None:
    settings = Settings(llm_provider="anthropic", _env_file=None)
    client = TestClient(create_app(settings), raise_server_exceptions=False)
    session = start(client)
    response = client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi", "expected_version": 0},
    )
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in error_of(response)["message"]


def test_malformed_model_output_is_200_with_warnings_and_no_change() -> None:
    client = client_with(ScriptedProvider(["not json", "still not json"]))
    session = start(client)
    result = say(client, session, "My name is Jane Smith")
    assert result["state"] == session["state"]
    assert result["warnings"] == ["malformed_output_retried", "malformed_output_fallback"]
    assert result["reply"].startswith("Sorry, I couldn't process that answer.")
    assert result["version"] == 1  # the exchange itself is recorded


def test_unexpected_error_is_500_without_internal_details() -> None:
    class Broken:
        name = "broken"

        def extract(self, ctx: TurnContext) -> TurnExtraction:
            raise RuntimeError("secret stack detail")

    client = client_with(Broken())
    session = start(client)
    response = client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi", "expected_version": 0},
    )
    assert response.status_code == 500
    assert error_of(response) == {
        "code": "internal_error",
        "message": "Something went wrong on our side.",
        "retryable": False,
    }


def test_direct_field_edit_applies_as_a_correction() -> None:
    client = client_with()
    session = say(client, start(client), "My name is Jane Smith")
    assert session["state"]["full_name"] == "Jane Smith"
    response = client.patch(
        f"/api/sessions/{session['id']}/fields",
        json={
            "path": "full_name",
            "value": "Jane A. Smith",
            "expected_version": session["version"],
        },
    )
    assert response.status_code == 200, response.text
    edited = response.json()
    assert edited["state"]["full_name"] == "Jane A. Smith"
    assert edited["version"] == session["version"] + 1
    assert "Jane A. Smith" in edited["document_markdown"]


def test_direct_edit_of_gifts_and_none_answers() -> None:
    client = client_with()
    session = start(client)
    response = client.patch(
        f"/api/sessions/{session['id']}/fields",
        json={
            "path": "specific_gifts",
            "value": [{"item": "piano", "recipient": "Ann"}],
            "expected_version": 0,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["state"]["specific_gifts"] == [{"item": "piano", "recipient": "Ann"}]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"path": "has_children", "value": "maybe"}, "has_children: 'has_children' must be"),
        ({"path": "full_name", "value": "  "}, "full_name: 'full_name' must not be empty"),
        ({"path": "favourite_colour", "value": "blue"}, "path:"),
    ],
)
def test_invalid_direct_edits_are_422(body: dict[str, Any], message: str) -> None:
    client = client_with()
    session = start(client)
    response = client.patch(
        f"/api/sessions/{session['id']}/fields", json={**body, "expected_version": 0}
    )
    assert response.status_code == 422
    assert error_of(response)["message"].startswith(message)


def test_document_download_is_markdown_attachment() -> None:
    client = client_with()
    session = say(client, start(client), "My name is Jane Smith")
    response = client.get(f"/api/sessions/{session['id']}/document")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert response.text == session["document_markdown"]
    assert "I, Jane Smith," in response.text


def test_openapi_contract_lists_every_endpoint() -> None:
    paths = client_with().get("/openapi.json").json()["paths"]
    assert set(paths) == {
        "/api/health",
        "/api/sessions",
        "/api/sessions/{session_id}",
        "/api/sessions/{session_id}/messages",
        "/api/sessions/{session_id}/fields",
        "/api/sessions/{session_id}/document",
    }


def test_fields_show_provenance_for_chat_answers_and_edits() -> None:
    client = client_with()
    session = say(client, start(client), "My name is Jane Smith")
    name = next(f for f in session["fields"] if f["path"] == "full_name")
    assert name["source"] == "chat"
    assert name["source_turn"] == 1
    assert name["evidence"] == "My name is Jane Smith"
    assert name["previous_value"] is None

    edited = client.patch(
        f"/api/sessions/{session['id']}/fields",
        json={"path": "full_name", "value": "Jane A. Smith", "expected_version": 1},
    ).json()
    name = next(f for f in edited["fields"] if f["path"] == "full_name")
    assert (name["source"], name["evidence"], name["previous_value"]) == (
        "edit",
        None,
        "Jane Smith",
    )
    missing = next(f for f in edited["fields"] if f["path"] == "home_address")
    assert missing["source"] is None and missing["evidence"] is None
