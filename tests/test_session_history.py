import json
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.db import session_manager


client = TestClient(app)


def test_partial_onboarding_uses_message_endpoint_not_chat_stream():
    """Onboarding selections persist via /message; /chat/stream is for replies only."""
    session_id = str(uuid.uuid4())

    with patch.object(session_manager, "save_message") as save_mock:
        response = client.post(
            f"/session/{session_id}/message",
            json={
                "role": "user",
                "content": "My experience level is: Entry-level.",
                "display_content": "Entry-level (0–2 years)",
                "metadata": {"step": "experience", "value": "Entry-level (0–2 years)"},
                "guest_id": "guest_test_1",
            },
        )

    assert response.status_code == 200
    save_mock.assert_called_once()
    assert save_mock.call_args.args[1] == "user"
    assert save_mock.call_args.kwargs["display_content"] == "Entry-level (0–2 years)"
    assert save_mock.call_args.kwargs["guest_id"] == "guest_test_1"


def test_chat_stream_profile_complete_uses_template_not_llm():
    """Profile-complete onboarding recommendations are templated (no LLM)."""
    session_id = str(uuid.uuid4())
    template_reply = (
        "**Federal Budgeting**\n"
        "\n"
        "**Duration:** 3 Days\n"
        "\n"
        "**Credits:** CLP: 24 | CPE: 24\n"
        "\n"
        "**Cost:** $1,429\n"
        "\n"
        "[Register Now](https://www.managementconcepts.com/product/4606)"
    )

    with patch.object(session_manager, "save_message") as save_mock, \
         patch(
             "src.chatbot.recommendations.build_template_recommendation_reply",
             return_value=template_reply,
         ), \
         patch("src.api.router.chat.get_or_create_chat_engine") as engine_mock:
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
    assert "Federal Budgeting" in response.text
    engine_mock.assert_not_called()
    assert save_mock.call_count == 2
    assert save_mock.call_args_list[1].args[1] == "assistant"
    assert save_mock.call_args_list[1].kwargs["metadata"]["template"] is True


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
                "guest_id": "guest_test_2",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "session_id": session_id}
    save_mock.assert_called_once()
    assert save_mock.call_args.kwargs["metadata"]["step"] == "welcome"
    assert save_mock.call_args.kwargs["guest_id"] == "guest_test_2"


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
    fake_session = {
        "session_id": session_id,
        "owner_id": "guest_x",
        "owner_type": "guest",
        "prefs": {"e": "Entry-level", "d": "Finance", "g": None},
        "prefs_expanded": {"experience": "Entry-level", "department": "Finance"},
        "stats": {"n": 1, "u": 1, "a": 0},
    }

    with patch.object(session_manager, "get_session_history_raw", return_value=fake_messages), \
         patch("src.db.profiles.get_session", return_value=fake_session):
        response = client.get(f"/session/{session_id}/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["messages"][0]["display_content"] == "Finance"
    assert payload["session"]["owner_id"] == "guest_x"


def test_start_session_accepts_guest_id():
    fake_session = {
        "session_id": "00000000-0000-0000-0000-000000000099",
        "owner_id": "guest_stable",
        "owner_type": "guest",
    }

    with patch("src.db.profiles.create_session", return_value=fake_session) as create_mock, \
         patch("src.db.profiles.get_learner_profile", return_value=None):
        response = client.post(
            "/session/start",
            json={"guest_id": "guest_stable"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["owner_id"] == "guest_stable"
    assert body["owner_type"] == "guest"
    assert "session_id" in body
    create_mock.assert_called_once()
    assert create_mock.call_args.kwargs["owner_id"] == "guest_stable"
    assert create_mock.call_args.kwargs["owner_type"] == "guest"


def test_start_session_prefers_user_id():
    fake_session = {
        "session_id": "00000000-0000-0000-0000-000000000088",
        "owner_id": "reg-42",
        "owner_type": "registered",
    }
    profile = {
        "owner_id": "reg-42",
        "owner_type": "registered",
        "experience": "Mid-level",
        "department": "IT",
        "goal": "Upskill",
        "profile_complete": True,
    }

    with patch("src.db.profiles.create_session", return_value=fake_session), \
         patch("src.db.profiles.get_learner_profile", return_value=profile):
        response = client.post(
            "/session/start",
            json={"user_id": "reg-42", "guest_id": "guest_ignored"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["owner_type"] == "registered"
    assert body["owner_id"] == "reg-42"
    assert body["profile"]["profile_complete"] is True


def test_get_history_rejects_invalid_session_id():
    response = client.get("/session/not-a-uuid/history")
    assert response.status_code == 400
