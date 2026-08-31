"""Tests for technical-support routing (non-course issues)."""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.chatbot.support import (
    CERTIFICATE_REQUEST_MESSAGE,
    OUT_OF_DOMAIN_MESSAGE,
    PASSWORD_CHANGE_MESSAGE,
    SPEAK_WITH_AGENT_CONFIRMATION,
    SPEAK_WITH_AGENT_OPTION,
    SUPPORT_TICKET_MESSAGE,
    classify_support_issue,
    is_out_of_domain_message,
    is_support_issue,
    out_of_domain_reply,
    support_options_for_message,
    support_reply_for_message,
)
from src.db import session_manager

client = TestClient(app)


def test_course_queries_are_not_support():
    assert not is_support_issue("What budgeting courses do you offer for finance?")
    assert not is_support_issue("Recommend project management training")
    assert not is_support_issue(
        "My experience level is: Mid-level. My department is: Finance. "
        "My career goal is: Earn a certification. Please recommend courses based on my profile.",
        metadata={"step": "goal", "profile_complete": True},
    )
    # Career-goal certification language is discovery, not cert printing
    assert classify_support_issue("I want to earn a certification in finance") is None


def test_password_change_is_support_ticket():
    assert classify_support_issue("I need to change my password") == "password"
    assert classify_support_issue("Please reset my password") == "password"
    assert is_support_issue("My password reset is not working")
    # Plurals + common typos must hit fixed support (not LLM old copy)
    assert classify_support_issue("i want to reset my passwords") == "password"
    assert classify_support_issue("i want to reset my passwrod") == "password"
    reply = support_reply_for_message("I need to change my password")
    assert reply == PASSWORD_CHANGE_MESSAGE
    assert "844-876-7476" in reply
    assert "technicalsupport@managementconcepts.com" in reply
    assert "speak with agent" in reply.lower()
    # Markdown formatting: scannable contact block, bold labels/CTA
    assert "**Phone:**" in reply
    assert "**Email:**" in reply
    assert "**Speak with Agent**" in reply
    assert "**password / login**" in reply
    assert "\n\n" in reply
    assert support_options_for_message("I need to change my password") == [
        SPEAK_WITH_AGENT_OPTION
    ]


def test_login_routes_to_password_style_ticket():
    assert classify_support_issue("I can't log in to my account") == "password"
    assert is_support_issue("I need a refund for a billing error")
    assert classify_support_issue("The website is broken and won't load") == "generic"


def test_agent_request_is_support():
    assert classify_support_issue("Can I speak with an agent?") == "agent"
    assert classify_support_issue("Speak with Agent") == "agent"
    assert is_support_issue("I want to talk to a real person")
    reply = support_reply_for_message("Speak with Agent")
    assert reply == SPEAK_WITH_AGENT_CONFIRMATION
    assert "844-876-7476" in reply
    assert "technicalsupport@managementconcepts.com" in reply
    assert "select speak with agent below" not in reply.lower()
    assert support_options_for_message("Speak with Agent") is None


def test_certificate_generation_request():
    assert classify_support_issue("Please generate my certificate") == "certificate"
    assert classify_support_issue("I need to print my certificate of completion") == "certificate"
    assert classify_support_issue("Can you download my course certificate?") == "certificate"
    reply = support_reply_for_message("Please generate my certificate")
    assert reply == CERTIFICATE_REQUEST_MESSAGE
    assert "generated shortly" in reply.lower()
    assert "844-876-7476" in reply
    assert "technicalsupport@managementconcepts.com" in reply
    assert support_options_for_message("Please generate my certificate") is None


def test_goal_step_never_routes_to_support():
    assert not is_support_issue(
        "I can't log in",
        metadata={"step": "goal", "profile_complete": True},
    )


def test_out_of_domain_cooking_not_support_or_rag():
    msg = "Teach me how to bake sourdough bread from scratch."
    assert is_out_of_domain_message(msg)
    assert not is_support_issue(msg)
    assert out_of_domain_reply() == OUT_OF_DOMAIN_MESSAGE
    assert "Management Concepts courses" in out_of_domain_reply()
    # Profile-complete onboarding never treated as OOD
    assert not is_out_of_domain_message(
        msg,
        metadata={"profile_complete": True, "step": "goal"},
    )
    # Course discovery not OOD
    assert not is_out_of_domain_message("Recommend project management courses")


def test_support_reply_content():
    assert support_reply_for_message("The website is broken and won't load") == SUPPORT_TICKET_MESSAGE
    assert support_reply_for_message("I need to change my password") == PASSWORD_CHANGE_MESSAGE
    assert support_reply_for_message("Please generate my certificate") == CERTIFICATE_REQUEST_MESSAGE
    assert support_reply_for_message("Speak with Agent") == SPEAK_WITH_AGENT_CONFIRMATION


def _assistant_meta(save_mock):
    """Extract assistant metadata from a save_messages turn batch."""
    turn = save_mock.call_args.args[1]
    return turn[1]["metadata"]


def test_chat_stream_returns_support_without_llm():
    session_id = str(uuid.uuid4())

    with patch.object(session_manager, "save_messages") as save_mock, \
         patch("src.api.router.chat.get_or_create_chat_engine") as engine_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": "I can't log in to the portal",
                "display_message": "I can't log in to the portal",
                "metadata": {"step": "free"},
                "guest_id": "guest_support_1",
            },
        )

    assert response.status_code == 200
    assert "844-876-7476" in response.text
    assert "technicalsupport@managementconcepts.com" in response.text
    assert "speak with agent" in response.text.lower()
    engine_mock.assert_not_called()
    assert save_mock.call_count == 1
    assert _assistant_meta(save_mock)["type"] == "support"
    assert _assistant_meta(save_mock)["options"] == [SPEAK_WITH_AGENT_OPTION]
    assert response.headers.get("x-mc-options")


def test_chat_stream_out_of_domain_without_llm():
    session_id = str(uuid.uuid4())

    with patch.object(session_manager, "save_messages") as save_mock, \
         patch("src.api.router.chat.get_or_create_chat_engine") as engine_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": "Teach me how to bake sourdough bread from scratch.",
                "metadata": {"step": "free"},
                "guest_id": "guest_ood_1",
            },
        )

    assert response.status_code == 200
    assert "Management Concepts courses" in response.text
    assert "product/" not in response.text
    engine_mock.assert_not_called()
    assert _assistant_meta(save_mock)["type"] == "out_of_domain"


def test_chat_stream_password_change():
    session_id = str(uuid.uuid4())

    with patch.object(session_manager, "save_messages") as save_mock, \
         patch("src.api.router.chat.get_or_create_chat_engine") as engine_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": "I need to change my password",
                "metadata": {"step": "free"},
                "guest_id": "guest_pw_1",
            },
        )

    assert response.status_code == 200
    assert "844-876-7476" in response.text
    assert "technicalsupport@managementconcepts.com" in response.text
    assert "speak with agent" in response.text.lower()
    assert "below" in response.text.lower()
    assert "**Phone:**" in response.text
    assert "**Email:**" in response.text
    engine_mock.assert_not_called()
    assistant_meta = _assistant_meta(save_mock)
    assert assistant_meta["support_kind"] == "password"
    assert assistant_meta["options"] == [SPEAK_WITH_AGENT_OPTION]


def test_chat_stream_certificate_request():
    session_id = str(uuid.uuid4())

    with patch.object(session_manager, "save_messages") as save_mock, \
         patch("src.api.router.chat.get_or_create_chat_engine") as engine_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": "Please generate my certificate",
                "metadata": {"step": "free"},
                "guest_id": "guest_cert_1",
            },
        )

    assert response.status_code == 200
    assert "generated shortly" in response.text.lower()
    assert "844-876-7476" in response.text
    assert "technicalsupport@managementconcepts.com" in response.text
    engine_mock.assert_not_called()
    assistant_meta = _assistant_meta(save_mock)
    assert assistant_meta["support_kind"] == "certificate"
    assert "options" not in assistant_meta


def test_chat_stream_speak_with_agent_confirmation():
    session_id = str(uuid.uuid4())

    with patch.object(session_manager, "save_messages") as save_mock, \
         patch("src.api.router.chat.get_or_create_chat_engine") as engine_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": "Speak with Agent",
                "metadata": {"step": "free"},
                "guest_id": "guest_support_2",
            },
        )

    assert response.status_code == 200
    assert "844-876-7476" in response.text
    assert "technicalsupport@managementconcepts.com" in response.text
    assert "select speak with agent below" not in response.text.lower()
    engine_mock.assert_not_called()
    assistant_meta = _assistant_meta(save_mock)
    assert assistant_meta["type"] == "support"
    assert assistant_meta.get("support_kind") == "agent"
    assert "options" not in assistant_meta


def test_chat_stream_course_query_is_not_support():
    session_id = str(uuid.uuid4())
    template_reply = (
        "Here are Management Concepts courses that match what you asked:\n\n"
        "**Federal Budgeting**\n\n"
        "[Register Now](https://www.managementconcepts.com/product/4606)"
    )

    with patch.object(session_manager, "save_messages") as save_mock, \
         patch(
             "src.chatbot.recommendations.build_template_recommendation_reply",
             return_value=template_reply,
         ) as rec_mock, \
         patch(
             "src.chatbot.query_context.enrich_metadata_with_durable_profile",
             side_effect=lambda m, **kw: dict(m or {}),
         ), \
         patch("src.api.router.chat.get_or_create_chat_engine") as engine_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": "What budgeting courses do you offer?",
                "metadata": {"step": "free"},
            },
        )

    assert response.status_code == 200
    assert "Federal Budgeting" in response.text
    rec_mock.assert_called_once()
    engine_mock.assert_not_called()
    assistant_meta = save_mock.call_args.args[1][1]["metadata"]
    assert assistant_meta.get("type") != "support"
