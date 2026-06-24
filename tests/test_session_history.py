import json
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.db import session_manager


client = TestClient(app)


def test_chat_stream_skips_llm_for_partial_onboarding():
    session_id = str(uuid.uuid4())

    with patch.object(session_manager, "save_message") as save_mock, \
         patch("src.api.main.get_or_create_chat_engine") as engine_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": "My experience level is: Entry-level.",
                "display_message": "Entry-level (0–2 years)",
                "metadata": {"step": "experience", "value": "Entry-level (0–2 years)"},
            },
        )

    assert response.status_code == 200
    assert response.text == ""
    engine_mock.assert_not_called()
    save_mock.assert_called_once()
    assert save_mock.call_args.args[1] == "user"
    assert save_mock.call_args.kwargs["display_content"] == "Entry-level (0–2 years)"


def test_chat_stream_calls_llm_when_profile_complete():
    session_id = str(uuid.uuid4())

    def fake_stream(engine, message):
        class FakeResponse:
            response_gen = iter(["Here are some courses."])

        return FakeResponse()

    with patch.object(session_manager, "get_llm_session_history", return_value=[]), \
         patch.object(session_manager, "save_message") as save_mock, \
         patch("src.chatbot.chatbot.get_streaming_response", side_effect=fake_stream), \
         patch("src.api.main.get_or_create_chat_engine", return_value=object()) as engine_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": (
                    "My experience level is: Entry-level. My department is: Finance. "
                    "My career goal is: Get a promotion. Please recommend courses."
                ),
                "display_message": "Get a promotion",
                "metadata": {
                    "step": "goal",
                    "profile_complete": True,
                    "profile": {
                        "experience": "Entry-level",
                        "department": "Finance",
                        "goal": "Get a promotion",
                    },
                },
            },
        )

    assert response.status_code == 200
    engine_mock.assert_called_once()
    assert save_mock.call_count == 2
    assert save_mock.call_args_list[1].args[1] == "assistant"


def test_save_session_message_endpoint():
    session_id = str(uuid.uuid4())

    with patch.object(session_manager, "save_message") as save_mock:
        response = client.post(
            f"/session/{session_id}/message",
            json={
                "role": "assistant",
                "content": "Welcome!",
                "display_content": "Welcome!",
                "metadata": {"step": "welcome", "type": "onboarding"},
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "session_id": session_id}
    save_mock.assert_called_once()
    assert save_mock.call_args.kwargs["metadata"]["step"] == "welcome"


def test_get_history_returns_display_content():
    session_id = str(uuid.uuid4())
    fake_messages = [
        {
            "role": "user",
            "content": "My department is: Finance. Please acknowledge.",
            "display_content": "Finance",
            "metadata": {"step": "department"},
            "created_at": "2026-06-23T14:30:00",
        }
    ]

    with patch.object(session_manager, "get_session_history_raw", return_value=fake_messages):
        response = client.get(f"/session/{session_id}/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["messages"][0]["display_content"] == "Finance"


def test_get_history_rejects_invalid_session_id():
    response = client.get("/session/not-a-uuid/history")
    assert response.status_code == 400