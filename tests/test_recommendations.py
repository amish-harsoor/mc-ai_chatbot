"""Tests for no-LLM profile recommendation templates and catalog field integrity."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from llama_index.core.schema import NodeWithScore, TextNode

from src.api.main import app
from src.chatbot.query_context import UserProfile
from src.chatbot.recommendations import (
    build_intro,
    build_profile_search_query,
    format_course_card,
    nodes_to_course_cards,
    should_use_template_recommendations,
)
from src.db import session_manager

client = TestClient(app)


def test_should_use_template_for_profile_complete():
    assert should_use_template_recommendations({"profile_complete": True}) is True
    assert (
        should_use_template_recommendations(
            {
                "step": "goal",
                "profile": {
                    "experience": "Entry-level",
                    "department": "Finance",
                    "goal": "Get a promotion",
                },
            }
        )
        is True
    )
    assert should_use_template_recommendations({"step": "free"}) is False
    assert should_use_template_recommendations(None) is False


def test_build_profile_search_query_includes_profile_fields():
    profile = UserProfile(
        experience="Mid-level (3–7 years)",
        department="Finance",
        goal="Earn a certification",
    )
    q = build_profile_search_query(profile)
    assert "Finance" in q
    assert "Mid-level" in q
    assert "certification" in q.lower() or "Earn a certification" in q


def test_format_course_card_preserves_official_fields():
    card = format_course_card(
        {
            "course_id": "4606",
            "course_title": "Federal Budgeting for Non-Budget Personnel",
            "duration": "3 Days",
            "level": "Intermediate",
            "credits": "CLP: 24 | CPE: 24",
            "price": "$1,429",
            "url": "https://www.managementconcepts.com/product/4606",
        },
        description="Learn federal budget formulation and execution basics.",
    )
    assert card is not None
    assert card == (
        "**Federal Budgeting for Non-Budget Personnel**\n"
        "\n"
        "**Duration:** 3 Days\n"
        "\n"
        "**Credits:** CLP: 24 | CPE: 24\n"
        "\n"
        "**Cost:** $1,429\n"
        "\n"
        "[Register Now](https://www.managementconcepts.com/product/4606)"
    )
    assert "Learn federal budget" not in card
    assert "Level:" not in card


def test_format_course_card_omits_missing_optional_fields():
    card = format_course_card(
        {"course_id": "1001", "course_title": "IT Acquisition"},
        description="Overview of IT acquisition.",
    )
    assert "Duration:" not in card
    assert "Level:" not in card
    assert "Cost:" not in card
    assert "**IT Acquisition**" in card
    assert "Overview of IT acquisition." not in card
    assert "[Register Now](" in card


def test_nodes_to_course_cards_uses_official_catalog_overlay():
    """Chunk metadata with weak titles must be replaced by official catalog when present."""
    profile = UserProfile(
        experience="Entry-level",
        department="Finance",
        goal="Upskill",
    )
    weak_node = NodeWithScore(
        node=TextNode(
            id_="n1",
            text=(
                "Course ID: 9999 | Title: Bad Title From Chunk\n"
                "This is a description of the course content for learners."
            ),
            metadata={
                "course_id": "9999",
                "course_title": "Bad Title From Chunk",
                "duration": "2 Days",
                "level": "Basic",
            },
        ),
        score=0.9,
    )

    official = {
        "course_id": "9999",
        "title": "Official Catalog Title",
        "course_title": "Official Catalog Title",
        "duration": "4 Days",
        "level": "Intermediate",
        "price": "$999",
        "url": "https://www.managementconcepts.com/product/9999",
    }

    with patch(
        "src.chatbot.recommendations.get_course",
        side_effect=lambda cid: official if str(cid) == "9999" else None,
    ), patch(
        "src.chatbot.recommendations.apply_official_catalog",
        side_effect=lambda meta: {**meta, **{k: v for k, v in official.items() if k != "course_id"}},
    ):
        cards = nodes_to_course_cards([weak_node], profile, max_courses=3)

    assert len(cards) == 1
    assert "**Official Catalog Title**" in cards[0]
    assert "Bad Title From Chunk" not in cards[0]
    assert "**Duration:** 4 Days" in cards[0]
    assert "Level:" not in cards[0]
    assert "**Cost:** $999" in cards[0]


def test_nodes_to_course_cards_dedupes_by_course_id():
    profile = UserProfile(department="IT")
    nodes = [
        NodeWithScore(
            node=TextNode(
                id_="a",
                text="Course ID: 1001 | Title: First\nAlpha description here.",
                metadata={"course_id": "1001", "course_title": "First"},
            ),
            score=1.0,
        ),
        NodeWithScore(
            node=TextNode(
                id_="b",
                text="Course ID: 1001 | Title: First Again\nBeta description.",
                metadata={"course_id": "1001", "course_title": "First Again"},
            ),
            score=0.8,
        ),
        NodeWithScore(
            node=TextNode(
                id_="c",
                text="Course ID: 1005 | Title: Second\nGamma description here.",
                metadata={"course_id": "1005", "course_title": "Second"},
            ),
            score=0.7,
        ),
    ]
    with patch("src.chatbot.recommendations.get_course", return_value=None), patch(
        "src.chatbot.recommendations.apply_official_catalog", side_effect=lambda m: dict(m)
    ), patch(
        "src.ingestion.pricing.apply_catalog_prices", side_effect=lambda m: m
    ):
        cards = nodes_to_course_cards(nodes, profile, max_courses=5)
    assert len(cards) == 2
    assert "**First**" in cards[0]
    assert "**Second**" in cards[1]
    assert cards[0].count("[Register Now](") == 1


def test_build_intro_includes_profile():
    intro = build_intro(
        UserProfile(experience="Entry-level", department="Finance", goal="Promotion")
    )
    assert "Finance" in intro
    assert "Entry-level" in intro
    assert "Promotion" in intro


def test_chat_stream_profile_complete_skips_llm():
    session_id = str(uuid.uuid4())
    template_reply = (
        "Based on your profile (Finance · Entry-level · Get a promotion), "
        "here are courses from the Management Concepts catalog:\n\n"
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

    with patch.object(session_manager, "save_messages") as save_mock, \
         patch(
             "src.chatbot.recommendations.build_template_recommendation_reply",
             return_value=template_reply,
         ) as rec_mock, \
         patch(
             "src.chatbot.query_context.enrich_metadata_with_durable_profile",
             side_effect=lambda m, **kw: dict(m or {}),
         ), \
         patch("src.api.router.chat.get_or_create_chat_engine") as engine_mock, \
         patch("src.chatbot.chatbot.get_streaming_response") as stream_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": (
                    "My experience level is: Entry-level. My department is: Finance. "
                    "My career goal is: Get a promotion. Please recommend courses based on my profile."
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
                    "experience": "Entry-level",
                    "department": "Finance",
                    "goal": "Get a promotion",
                },
                "guest_id": "guest_template_1",
            },
        )

    assert response.status_code == 200
    assert "**Federal Budgeting**" in response.text
    assert "**Duration:** 3 Days" in response.text
    assert response.text.count("[Register Now](") == 1
    assert "[Federal Budgeting](" not in response.text
    rec_mock.assert_called_once()
    engine_mock.assert_not_called()
    stream_mock.assert_not_called()
    assert save_mock.call_count == 1
    assistant_meta = save_mock.call_args.args[1][1]["metadata"]
    assert assistant_meta["type"] == "profile_recommendation"
    assert assistant_meta["template"] is True


def test_chat_stream_free_chat_still_uses_llm():
    session_id = str(uuid.uuid4())

    def fake_stream(engine, message):
        class FakeResponse:
            response_gen = iter(["Here are some courses."])

        return FakeResponse()

    with patch.object(session_manager, "get_llm_session_history", return_value=[]), \
         patch.object(session_manager, "save_messages"), \
         patch(
             "src.chatbot.query_context.enrich_metadata_with_durable_profile",
             side_effect=lambda m, **kw: dict(m or {}),
         ), \
         patch("src.chatbot.chatbot.get_streaming_response", side_effect=fake_stream), \
         patch("src.api.router.chat.get_or_create_chat_engine", return_value=object()) as engine_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": "What budgeting courses do you offer?",
                "metadata": {"step": "free"},
            },
        )

    assert response.status_code == 200
    assert response.text == "Here are some courses."
    engine_mock.assert_called_once()


def test_chat_stream_template_failure_falls_back_to_llm():
    session_id = str(uuid.uuid4())

    def fake_stream(engine, message):
        class FakeResponse:
            response_gen = iter(["LLM fallback courses."])

        return FakeResponse()

    with patch.object(session_manager, "get_llm_session_history", return_value=[]), \
         patch.object(session_manager, "save_messages"), \
         patch(
             "src.chatbot.query_context.enrich_metadata_with_durable_profile",
             side_effect=lambda m, **kw: dict(m or {}),
         ), \
         patch(
             "src.chatbot.recommendations.build_template_recommendation_reply",
             side_effect=RuntimeError("retrieval down"),
         ), \
         patch("src.chatbot.chatbot.get_streaming_response", side_effect=fake_stream), \
         patch("src.api.router.chat.get_or_create_chat_engine", return_value=object()) as engine_mock:
        response = client.post(
            "/chat/stream",
            json={
                "session_id": session_id,
                "message": "Please recommend courses based on my profile.",
                "metadata": {
                    "step": "goal",
                    "profile_complete": True,
                    "profile": {
                        "experience": "Entry-level",
                        "department": "Finance",
                        "goal": "Upskill",
                    },
                },
            },
        )

    assert response.status_code == 200
    assert response.text == "LLM fallback courses."
    engine_mock.assert_called_once()
