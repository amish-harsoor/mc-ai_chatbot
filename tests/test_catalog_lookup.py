"""Tests for zero-LLM course-ID fact lookup from the official catalog."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.chatbot.catalog_lookup import (
    build_catalog_lookup_reply,
    detect_requested_fields,
    extract_lookup_course_ids,
    format_course_fact_card,
    should_use_catalog_lookup,
)
from src.db import session_manager

client = TestClient(app)

SAMPLE_4606 = {
    "course_id": "4606",
    "title": "Introduction to Data Visualization",
    "course_title": "Introduction to Data Visualization",
    "duration": "2 Days",
    "level": "Intermediate",
    "credits": "CLP: 16 | CPE: 16",
    "url": "https://www.managementconcepts.com/product/4606",
    "price": "$1409.00",
}

SAMPLE_1001 = {
    "course_id": "1001",
    "title": "Information Technology (IT) Acquisition",
    "course_title": "Information Technology (IT) Acquisition",
    "duration": "3 Days",
    "level": "Intermediate",
    "url": "https://www.managementconcepts.com/product/1001",
    "price": "$1,200",
}


def test_extract_lookup_ids_from_course_phrase():
    assert extract_lookup_course_ids("What's the cost of course 4606?") == ["4606"]
    assert extract_lookup_course_ids(
        "See https://www.managementconcepts.com/product/1001"
    ) == ["1001"]


def test_extract_bare_id_when_fact_intent():
    assert extract_lookup_course_ids("How much is 4606?") == ["4606"]
    # No fact intent → do not treat random numbers as course ids
    assert extract_lookup_course_ids("I have worked for 4606 days") == []


def test_should_use_catalog_lookup_for_fact_questions():
    assert should_use_catalog_lookup("What's the cost of course 4606?") is True
    assert should_use_catalog_lookup("Tell me about course 4606") is True
    assert should_use_catalog_lookup("duration of course 1001") is True
    assert should_use_catalog_lookup("What is the level for course 4606?") is True


def test_should_not_use_catalog_lookup_for_discovery_or_profile():
    assert (
        should_use_catalog_lookup(
            "Please recommend courses like 4606 based on my profile"
        )
        is False
    )
    assert (
        should_use_catalog_lookup(
            "What's the cost of course 4606?",
            metadata={"profile_complete": True},
        )
        is False
    )
    assert should_use_catalog_lookup("What budgeting courses do you offer?") is False
    assert should_use_catalog_lookup("hello") is False


def test_detect_requested_fields():
    assert detect_requested_fields("What's the cost of course 4606?") == ["cost"]
    assert "duration" in detect_requested_fields("How long is course 4606?")
    assert "level" in detect_requested_fields("What level is course 4606?")


def test_format_course_fact_card_preserves_official_fields():
    card = format_course_fact_card(SAMPLE_4606, fields=["cost"])
    assert card == (
        "**Introduction to Data Visualization**\n"
        "\n"
        "**Duration:** 2 Days\n"
        "\n"
        "**Credits:** CLP: 16 | CPE: 16\n"
        "\n"
        "**Cost:** $1409.00\n"
        "\n"
        "[Register Now](https://www.managementconcepts.com/product/4606)"
    )
    assert "Level:" not in card


def test_build_reply_cost_question():
    with patch(
        "src.chatbot.catalog_lookup.get_course",
        side_effect=lambda cid: SAMPLE_4606 if str(cid) == "4606" else None,
    ):
        reply = build_catalog_lookup_reply("What's the cost of course 4606?")
    assert reply is not None
    assert "Introduction to Data Visualization" in reply
    assert "$1409.00" in reply
    assert "**Introduction to Data Visualization**" in reply
    assert reply.count("[Register Now](") == 1


def test_build_reply_unknown_course():
    with patch("src.chatbot.catalog_lookup.get_course", return_value=None):
        reply = build_catalog_lookup_reply("What's the cost of course 99999?")
    assert reply is not None
    assert "couldn't find" in reply.lower()
    assert "99999" in reply


def test_build_reply_missing_price_says_not_listed():
    entry = {**SAMPLE_4606, "price": None}
    with patch("src.chatbot.catalog_lookup.get_course", return_value=entry), patch(
        "src.ingestion.pricing.lookup_course_price", return_value=None
    ):
        reply = build_catalog_lookup_reply("How much does course 4606 cost?")
    assert reply is not None
    assert "not listed" in reply.lower()
    assert "Introduction to Data Visualization" in reply


def test_build_reply_two_courses():
    def fake_get(cid):
        cid = str(cid)
        if cid == "4606":
            return SAMPLE_4606
        if cid == "1001":
            return SAMPLE_1001
        return None

    with patch("src.chatbot.catalog_lookup.get_course", side_effect=fake_get):
        reply = build_catalog_lookup_reply(
            "What is the cost of course 4606 and course 1001?"
        )
    assert reply is not None
    assert "**Introduction to Data Visualization**" in reply
    assert "**Information Technology (IT) Acquisition**" in reply
    assert reply.count("[Register Now](") == 2


def test_chat_stream_catalog_lookup_skips_llm():
    session_id = str(uuid.uuid4())
    with patch.object(session_manager, "save_messages") as save_mock, \
         patch(
             "src.chatbot.catalog_lookup.get_course",
             return_value=SAMPLE_4606,
         ), \
         patch("src.api.router.chat.get_or_create_chat_engine") as engine_mock, \
         patch("src.chatbot.chatbot.get_streaming_response") as stream_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": "What's the cost of course 4606?",
                "metadata": {"step": "free"},
                "guest_id": "guest_lookup_1",
            },
        )

    assert response.status_code == 200
    assert "**Introduction to Data Visualization**" in response.text
    assert "$1409.00" in response.text
    assert response.text.count("[Register Now](") == 1
    assert "[Introduction to Data Visualization](" not in response.text
    engine_mock.assert_not_called()
    stream_mock.assert_not_called()
    assert save_mock.call_count == 1
    turn = save_mock.call_args.args[1]
    assert turn[1]["metadata"]["type"] == "catalog_lookup"
    assert turn[1]["metadata"]["template"] is True


def test_chat_stream_topic_query_uses_template_not_catalog_lookup():
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
    assert assistant_meta.get("type") != "catalog_lookup"
