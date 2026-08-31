"""Tests for no-LLM profile recommendation templates and catalog field integrity."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from llama_index.core.schema import NodeWithScore, TextNode

from src.api.main import app
from src.chatbot.query_context import UserProfile
from src.chatbot.recommendations import (
    _department_key,
    _keyword_hits,
    build_intro,
    build_profile_search_query,
    catalog_profile_fit,
    department_topic_score,
    format_course_card,
    goal_fit_score,
    level_fit_score,
    looks_like_recommendation_request,
    looks_like_topic_query,
    nodes_to_course_cards,
    query_title_score,
    rank_courses_for_profile,
    should_use_template_recommendations,
)
from src.db import session_manager

client = TestClient(app)


def _catalog_fixture() -> dict[str, dict]:
    """Small official-catalog stand-in for ranking tests."""
    return {
        "4606": {
            "course_id": "4606",
            "title": "Federal Budgeting for Non-Budget Personnel",
            "course_title": "Federal Budgeting for Non-Budget Personnel",
            "duration": "3 Days",
            "level": "Basic",
            "credits": "CLP: 24 | CPE: 24",
            "price": "$1,429",
            "url": "https://www.managementconcepts.com/product/4606",
        },
        "1001": {
            "course_id": "1001",
            "title": "Information Technology (IT) Acquisition",
            "course_title": "Information Technology (IT) Acquisition",
            "duration": "5 Days",
            "level": "Intermediate",
            "price": "$2,000",
            "url": "https://www.managementconcepts.com/product/1001",
        },
        "4450": {
            "course_id": "4450",
            "title": "Supervisory Leadership Skills",
            "course_title": "Supervisory Leadership Skills",
            "duration": "3 Days",
            "level": "Intermediate",
            "price": "$1,500",
            "url": "https://www.managementconcepts.com/product/4450",
        },
        "1012": {
            "course_id": "1012",
            "title": "Advanced Source Selection",
            "course_title": "Advanced Source Selection",
            "duration": "5 Days",
            "level": "Advanced",
            "url": "https://www.managementconcepts.com/product/1012",
        },
        "9500": {
            "course_id": "9500",
            "title": "Individual Coaching with an Associate Level Certified Coach (ACC)",
            "course_title": "Individual Coaching with an Associate Level Certified Coach (ACC)",
            "level": "Intermediate",
            "url": "https://www.managementconcepts.com/product/9500",
        },
        "9999": {
            "course_id": "9999",
            "title": "Official Catalog Title",
            "course_title": "Official Catalog Title",
            "duration": "4 Days",
            "level": "Intermediate",
            "price": "$999",
            "url": "https://www.managementconcepts.com/product/9999",
        },
    }


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


_COMPLETE_FREE_PROFILE = {
    "step": "free",
    "experience": "Mid-level (3–7 years)",
    "department": "Finance",
    "goal": "Get a promotion",
    "profile": {
        "experience": "Mid-level (3–7 years)",
        "department": "Finance",
        "goal": "Get a promotion",
    },
}


def test_looks_like_recommendation_request():
    assert looks_like_recommendation_request(
        "yes, give me a list of courses best suited for my experience"
    )
    assert looks_like_recommendation_request("Please recommend courses based on my profile.")
    assert looks_like_recommendation_request("show me courses for me")
    assert looks_like_recommendation_request("What budgeting courses do you offer?")
    assert looks_like_recommendation_request("I want a PMP certification")
    assert not looks_like_recommendation_request("What is the cost of course 4606?")
    assert not looks_like_recommendation_request("hello")
    assert not looks_like_recommendation_request("")


def test_looks_like_topic_query():
    assert looks_like_topic_query("PMP")
    assert looks_like_topic_query("budgeting")
    assert looks_like_topic_query("project management")
    assert not looks_like_topic_query("hello")
    assert not looks_like_topic_query("thanks")
    assert not looks_like_topic_query("")


def test_should_use_template_for_free_chat_rec_without_profile():
    assert (
        should_use_template_recommendations(
            {"step": "free"},
            latest_message="yes, give me a list of courses best suited for my experience",
        )
        is True
    )
    assert should_use_template_recommendations({}, latest_message="PMP") is True
    assert should_use_template_recommendations(None, latest_message="hello") is False
    assert (
        should_use_template_recommendations(
            _COMPLETE_FREE_PROFILE,
            latest_message="What is the cost of course 4606?",
        )
        is False
    )


def test_should_use_template_for_free_chat_rec_with_complete_profile():
    assert (
        should_use_template_recommendations(
            _COMPLETE_FREE_PROFILE,
            latest_message="yes, give me a list of courses best suited for my experience",
        )
        is True
    )
    assert (
        should_use_template_recommendations(
            _COMPLETE_FREE_PROFILE,
            latest_message="What is the cost of course 4606?",
        )
        is False
    )


def test_build_profile_search_query_includes_profile_fields():
    profile = UserProfile(
        experience="Mid-level (3–7 years)",
        department="Finance",
        goal="Earn a certification",
    )
    q = build_profile_search_query(profile)
    # Catalog-aligned finance phrases (not only the raw department label).
    assert "budget" in q.lower() or "financial" in q.lower()
    assert "Mid-level" in q
    assert "certification" in q.lower() or "Earn a certification" in q


def test_department_topic_prefers_on_topic_titles():
    finance_entry = {"title": "Federal Budget Formulation"}
    it_entry = {"title": "Information Technology (IT) Acquisition"}
    profile = UserProfile(department="Finance")
    assert department_topic_score(finance_entry, profile) > 0
    assert department_topic_score(it_entry, profile) == 0


def test_department_key_does_not_false_match_it_substring():
    assert _department_key("IT") == "it"
    assert _department_key("Finance") == "finance"
    assert _department_key("Management") == "management"
    assert _department_key("information technology") == "it"
    # Raw substring "it" inside unrelated words must not map to IT.
    assert _department_key("facilities") is None
    assert _department_key("security") is None
    assert _department_key("unit") is None
    assert _department_key("Human Resources") is None


def test_keyword_hits_longest_match_dedupes_overlap():
    # cyber + cybersecurity should count once, not twice.
    assert _keyword_hits("cybersecurity fundamentals", ("cyber", "cybersecurity")) == 1
    assert _keyword_hits(
        "basic appropriations law",
        ("appropriation", "appropriations"),
    ) == 1


def test_goal_fit_compound_upskill_personal_growth():
    profile = UserProfile(goal="Upskill / personal growth")
    skills = {"title": "Management Skills Workshop"}
    ei = {"title": "Emotional Intelligence for Leaders"}
    assert goal_fit_score(skills, profile) > 0
    # "personal growth" keywords must still apply even though "upskill" matches first.
    assert goal_fit_score(ei, profile) > 0


def test_management_topic_ignores_financial_manager_titles():
    profile = UserProfile(department="Management")
    leadership = {"title": "Advanced Leadership Skills and Techniques"}
    finance_mgr = {"title": "Data Analysis for Financial Managers Using Microsoft Excel"}
    assert department_topic_score(leadership, profile) > 0
    assert department_topic_score(finance_mgr, profile) == 0


def test_level_fit_entry_vs_advanced():
    basic = {"level": "Basic"}
    advanced = {"level": "Advanced"}
    entry = UserProfile(experience="Entry-level (0–2 years)")
    senior = UserProfile(experience="Senior/Manager (8+ years)")
    assert level_fit_score(basic, entry) > level_fit_score(advanced, entry)
    assert level_fit_score(advanced, senior) > level_fit_score(basic, senior)


def test_catalog_profile_fit_penalizes_coaching_packages():
    core = {
        "title": "Federal Budgeting for Non-Budget Personnel",
        "level": "Basic",
    }
    coach = {
        "title": "Individual Coaching with a Professional Certified Coach (PCC)",
        "level": "Intermediate",
    }
    profile = UserProfile(
        experience="Entry-level (0–2 years)",
        department="Finance",
        goal="Upskill / personal growth",
    )
    assert catalog_profile_fit(core, profile) > catalog_profile_fit(coach, profile)


def test_rank_courses_for_profile_prefers_department_and_level():
    catalog = _catalog_fixture()
    profile = UserProfile(
        experience="Entry-level (0–2 years)",
        department="Finance",
        goal="Upskill / personal growth",
    )
    # Retrieval only surfaces an IT course — catalog ranking should still pick finance.
    nodes = [
        NodeWithScore(
            node=TextNode(
                id_="n1",
                text="IT Acquisition",
                metadata={"course_id": "1001", "course_title": "Information Technology (IT) Acquisition"},
            ),
            score=0.99,
        )
    ]
    with patch(
        "src.chatbot.recommendations.load_course_catalog",
        return_value=catalog,
    ), patch(
        "src.chatbot.recommendations.get_course",
        side_effect=lambda cid: catalog.get(str(cid)),
    ), patch(
        "src.chatbot.recommendations.apply_official_catalog",
        side_effect=lambda m: dict(m),
    ), patch(
        "src.ingestion.pricing.apply_catalog_prices",
        side_effect=lambda m: m,
    ):
        ranked = rank_courses_for_profile(profile, nodes, max_courses=3)

    ids = [r["course_id"] for r in ranked]
    assert ids, "expected catalog-ranked courses"
    assert ids[0] == "4606"
    assert "9500" not in ids  # coaching package
    assert "1001" not in ids or ids.index("4606") < ids.index("1001")


def test_query_title_score_prefers_phrase_match():
    pmp = {"title": "PMP® Exam Prep (PMI® Authorized)"}
    budget = {"title": "Federal Budgeting for Non-Budget Personnel"}
    it = {"title": "Information Technology (IT) Acquisition"}
    assert query_title_score(pmp, "PMP") > query_title_score(budget, "PMP")
    assert query_title_score(budget, "budgeting courses") > query_title_score(it, "budgeting courses")
    assert query_title_score(it, "hello") == 0


def test_rank_courses_by_query_without_profile():
    catalog = _catalog_fixture()
    catalog["6137"] = {
        "course_id": "6137",
        "title": "PMP® Exam Prep (PMI® Authorized)",
        "course_title": "PMP® Exam Prep (PMI® Authorized)",
        "duration": "5 Days",
        "level": "Intermediate",
        "credits": "CLP: 40 | CPE: 40",
        "price": "$3,059",
        "url": "https://www.managementconcepts.com/product/6137",
    }
    profile = UserProfile()
    with patch(
        "src.chatbot.recommendations.load_course_catalog",
        return_value=catalog,
    ), patch(
        "src.chatbot.recommendations.get_course",
        side_effect=lambda cid: catalog.get(str(cid)),
    ), patch(
        "src.chatbot.recommendations.apply_official_catalog",
        side_effect=lambda m: dict(m),
    ), patch(
        "src.ingestion.pricing.apply_catalog_prices",
        side_effect=lambda m: m,
    ):
        ranked = rank_courses_for_profile(
            profile, [], max_courses=3, query="PMP"
        )

    ids = [r["course_id"] for r in ranked]
    assert ids[0] == "6137"
    assert "9500" not in ids


def test_rank_defers_hard_level_mismatch_for_senior():
    catalog = _catalog_fixture()
    # Leadership at Basic should not beat Advanced leadership for senior managers.
    catalog["4000"] = {
        "course_id": "4000",
        "title": "Leadership and Management Skills for Non-Managers",
        "course_title": "Leadership and Management Skills for Non-Managers",
        "level": "Basic",
        "url": "https://www.managementconcepts.com/product/4000",
    }
    catalog["4002"] = {
        "course_id": "4002",
        "title": "Advanced Leadership Skills and Techniques",
        "course_title": "Advanced Leadership Skills and Techniques",
        "level": "Advanced",
        "url": "https://www.managementconcepts.com/product/4002",
    }
    profile = UserProfile(
        experience="Senior/Manager (8+ years)",
        department="Management",
        goal="Get a promotion",
    )
    with patch(
        "src.chatbot.recommendations.load_course_catalog",
        return_value=catalog,
    ), patch(
        "src.chatbot.recommendations.get_course",
        side_effect=lambda cid: catalog.get(str(cid)),
    ), patch(
        "src.chatbot.recommendations.apply_official_catalog",
        side_effect=lambda m: dict(m),
    ), patch(
        "src.ingestion.pricing.apply_catalog_prices",
        side_effect=lambda m: m,
    ):
        ranked = rank_courses_for_profile(profile, [], max_courses=3)

    ids = [r["course_id"] for r in ranked]
    assert "4002" in ids
    # Basic leadership is deferred (or dropped) behind Advanced for seniors.
    if "4000" in ids:
        assert ids.index("4002") < ids.index("4000")
    else:
        assert ids[0] == "4002"


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
        experience="Mid-level (3–7 years)",
        department="Management",
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

    catalog = _catalog_fixture()
    # Give 9999 a management-relevant title so it passes the department gate.
    catalog["9999"] = {
        **catalog["9999"],
        "title": "Official Catalog Title Leadership Workshop",
        "course_title": "Official Catalog Title Leadership Workshop",
    }

    with patch(
        "src.chatbot.recommendations.load_course_catalog",
        return_value=catalog,
    ), patch(
        "src.chatbot.recommendations.get_course",
        side_effect=lambda cid: catalog.get(str(cid)),
    ), patch(
        "src.chatbot.recommendations.apply_official_catalog",
        side_effect=lambda meta: {
            **meta,
            **{k: v for k, v in (catalog.get(str(meta.get("course_id") or ""), {})).items()},
        },
    ), patch(
        "src.ingestion.pricing.apply_catalog_prices",
        side_effect=lambda m: m,
    ):
        cards = nodes_to_course_cards([weak_node], profile, max_courses=3)

    assert cards
    assert any("Official Catalog Title Leadership Workshop" in c for c in cards)
    assert "Bad Title From Chunk" not in "".join(cards)
    assert any("**Duration:** 4 Days" in c for c in cards)
    assert "Level:" not in "".join(cards)
    assert any("**Cost:** $999" in c for c in cards)


def test_nodes_to_course_cards_dedupes_by_course_id():
    profile = UserProfile(
        experience="Mid-level (3–7 years)",
        department="IT",
        goal="Upskill",
    )
    catalog = {
        "1001": {
            "course_id": "1001",
            "title": "Information Technology (IT) Acquisition",
            "course_title": "Information Technology (IT) Acquisition",
            "level": "Intermediate",
            "url": "https://www.managementconcepts.com/product/1001",
        },
        "1005": {
            "course_id": "1005",
            "title": "IT Systems Project Management",
            "course_title": "IT Systems Project Management",
            "level": "Intermediate",
            "url": "https://www.managementconcepts.com/product/1005",
        },
    }
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
    with patch(
        "src.chatbot.recommendations.load_course_catalog",
        return_value=catalog,
    ), patch(
        "src.chatbot.recommendations.get_course",
        side_effect=lambda cid: catalog.get(str(cid)),
    ), patch(
        "src.chatbot.recommendations.apply_official_catalog",
        side_effect=lambda m: dict(m),
    ), patch(
        "src.ingestion.pricing.apply_catalog_prices",
        side_effect=lambda m: m,
    ):
        cards = nodes_to_course_cards(nodes, profile, max_courses=5)
    assert len(cards) == 2
    joined = "\n".join(cards)
    assert "Information Technology (IT) Acquisition" in joined
    assert "IT Systems Project Management" in joined
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


def test_chat_stream_free_rec_request_with_profile_uses_template():
    session_id = str(uuid.uuid4())
    template_reply = (
        "Based on your profile (Finance · Mid-level (3–7 years) · Get a promotion), "
        "here are courses from the Management Concepts catalog:\n\n"
        "**Federal Budgeting**\n"
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
                "message": "yes, give me a list of courses best suited for my experience",
                "metadata": {
                    "step": "free",
                    "experience": "Mid-level (3–7 years)",
                    "department": "Finance",
                    "goal": "Get a promotion",
                    "profile": {
                        "experience": "Mid-level (3–7 years)",
                        "department": "Finance",
                        "goal": "Get a promotion",
                    },
                },
                "guest_id": "guest_template_free_rec",
            },
        )

    assert response.status_code == 200
    assert "**Federal Budgeting**" in response.text
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
            response_gen = iter(["Online and in-person sessions both count toward credits."])

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
                "message": "How does online delivery differ from classroom sessions?",
                "metadata": {"step": "free"},
            },
        )

    assert response.status_code == 200
    assert "Online and in-person" in response.text
    engine_mock.assert_called_once()


def test_chat_stream_topic_query_without_profile_uses_template():
    session_id = str(uuid.uuid4())
    template_reply = (
        "Here are Management Concepts courses that match what you asked:\n\n"
        "**PMP® Exam Prep (PMI® Authorized)**\n"
        "\n"
        "**Duration:** 5 Days\n"
        "\n"
        "[Register Now](https://www.managementconcepts.com/product/6137)"
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
                "message": "PMP",
                "guest_id": "guest_pmp_topic",
            },
        )

    assert response.status_code == 200
    assert "PMP® Exam Prep" in response.text
    rec_mock.assert_called_once()
    engine_mock.assert_not_called()
    stream_mock.assert_not_called()
    assert save_mock.call_count == 1


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
