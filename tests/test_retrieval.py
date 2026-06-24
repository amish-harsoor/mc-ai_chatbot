from unittest.mock import MagicMock, patch

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores import FilterOperator

from src.chatbot import retrieval
from src.chatbot.query_context import (
    build_metadata_filters,
    build_query_expansion_terms,
    build_user_profile,
)
from src.chatbot.retrieval import QueryExpansionRetriever, _load_bm25_nodes, build_condense_prompt


def test_build_user_profile_from_metadata_profile_dict():
    profile = build_user_profile(
        [],
        latest_message="Please recommend courses.",
        request_metadata={
            "step": "goal",
            "profile_complete": True,
            "profile": {
                "experience": "Mid-level (3–7 years)",
                "department": "IT",
                "goal": "Earn a certification",
            },
        },
    )
    assert profile.experience == "Mid-level (3–7 years)"
    assert profile.department == "IT"
    assert profile.goal == "Earn a certification"


def test_build_user_profile_from_chat_history():
    history = [
        ChatMessage(
            role=MessageRole.USER,
            content="My experience level is: Entry-level (0-2 years). Please acknowledge.",
        ),
        ChatMessage(
            role=MessageRole.USER,
            content="My department is: Finance. Please acknowledge.",
        ),
        ChatMessage(
            role=MessageRole.USER,
            content="My career goal is: Get a promotion. Please recommend courses.",
        ),
    ]

    profile = build_user_profile(history)
    assert profile.experience == "Entry-level (0-2 years)"
    assert profile.department == "Finance"
    assert profile.goal == "Get a promotion"


def test_build_metadata_filters_skips_department():
    profile = build_user_profile(
        [],
        latest_message="My department is: Finance. Please acknowledge.",
    )
    filters = build_metadata_filters(profile)
    assert filters is None


def test_build_metadata_filters_for_course_id():
    profile = build_user_profile([], latest_message="Tell me about course 4606")
    filters = build_metadata_filters(profile)
    assert filters is not None
    assert filters.filters[0].key == "course_id"
    assert filters.filters[0].value == "4606"
    assert filters.filters[0].operator == FilterOperator.EQ


def test_build_query_expansion_terms():
    profile = build_user_profile(
        [],
        latest_message="My department is: Finance. My career goal is: Get a promotion.",
    )
    terms = build_query_expansion_terms(profile)
    assert any("Finance" in term for term in terms)
    assert any("promotion" in term for term in terms)


def test_build_condense_prompt_includes_profile():
    profile = build_user_profile(
        [],
        latest_message="My department is: IT. My career goal is: Earn a certification.",
    )
    prompt = build_condense_prompt(profile)
    assert "Department: IT" in prompt
    assert "Career goal: Earn a certification" in prompt


def test_query_expansion_retriever_merges_profile_terms():
    class StubRetriever:
        last_query = None

        def retrieve(self, query_bundle):
            StubRetriever.last_query = query_bundle.query_str
            return []

    profile = build_user_profile([], latest_message="My department is: Finance.")
    retriever = QueryExpansionRetriever(StubRetriever(), profile=profile)
    retriever.retrieve("budget analysis")

    assert "budget analysis" in StubRetriever.last_query
    assert "Finance" in StubRetriever.last_query


def test_load_bm25_nodes_queries_postgres_directly():
    retrieval._bm25_nodes_cache = None
    mock_rows = [
        {"node_id": "n1", "text": "Budget course", "metadata_": {"course_id": "4606"}},
        {"node_id": "n2", "text": "Finance basics", "metadata_": {}},
    ]
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = mock_rows
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("src.chatbot.retrieval.psycopg2.connect", return_value=mock_conn), patch(
        "src.chatbot.retrieval.get_vector_table_name", return_value="data_vectors"
    ):
        nodes = _load_bm25_nodes(MagicMock())

    assert len(nodes) == 2
    assert isinstance(nodes[0], TextNode)
    assert nodes[0].metadata["course_id"] == "4606"
    mock_cursor.execute.assert_called_once()
    assert "SELECT node_id, text, metadata_" in mock_cursor.execute.call_args[0][0]