import json
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.db import session_manager


client = TestClient(app)


def test_chat_stream_saves_display_and_metadata():
    session_id = str(uuid.uuid4())

    def fake_stream(engine, message):
        class FakeResponse:
            response_gen = iter(["Hello there!"])

        return FakeResponse()

    with patch.object(session_manager, "get_session_history", return_value=[]), \
         patch.object(session_manager, "save_message") as save_mock, \
         patch("src.chatbot.chatbot.get_streaming_response", side_effect=fake_stream), \
         patch("src.chatbot.chatbot.create_chat_engine", return_value=object()):
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": "My experience level is: Entry-level. Please acknowledge.",
                "display_message": "Entry-level (0–2 years)",
                "silent_response": True,
                "metadata": {"step": "experience"},
            },
        )

    assert response.status_code == 200
    assert save_mock.call_count == 2

    user_call = save_mock.call_args_list[0]
    assert user_call.args[0] == session_id
    assert user_call.args[1] == "user"
    assert user_call.kwargs["display_content"] == "Entry-level (0–2 years)"
    assert user_call.kwargs["metadata"] == {"step": "experience"}

    assistant_call = save_mock.call_args_list[1]
    assert assistant_call.args[1] == "assistant"
    assert assistant_call.kwargs["metadata"] == {"visible": False}


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