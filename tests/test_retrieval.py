from unittest.mock import MagicMock, patch

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.core.vector_stores import FilterOperator

from src.chatbot import retrieval
from src.chatbot.query_context import (
    build_metadata_filters,
    build_query_expansion_terms,
    build_user_profile,
    enrich_metadata_with_durable_profile,
    extract_course_ids_from_text,
)
from src.chatbot.retrieval import (
    CourseMetadataPostprocessor,
    MetadataPostFilterRetriever,
    QueryExpansionRetriever,
    _load_bm25_nodes,
    build_condense_prompt,
    create_hybrid_retriever,
    create_node_postprocessors,
)


def test_build_user_profile_from_free_step_metadata():
    profile = build_user_profile(
        [],
        latest_message="Tell me about budgeting courses",
        request_metadata={
            "step": "free",
            "profile": {
                "experience": "Mid-level (3–7 years)",
                "department": "Finance",
                "goal": "Earn a certification",
            },
            "experience": "Mid-level (3–7 years)",
            "department": "Finance",
            "goal": "Earn a certification",
        },
    )
    assert profile.department == "Finance"
    assert profile.goal == "Earn a certification"


def test_enrich_metadata_with_durable_profile_fills_gaps():
    with patch(
        "src.db.profiles.get_session",
        return_value={
            "owner_id": "guest_1",
            "prefs_expanded": {
                "experience": "Entry-level",
                "department": "Finance",
                "goal": "Get a promotion",
            },
        },
    ), patch("src.db.profiles.get_learner_profile", return_value=None):
        enriched = enrich_metadata_with_durable_profile(
            {"step": "free"},
            session_id="sess-1",
        )
    assert enriched["experience"] == "Entry-level"
    assert enriched["department"] == "Finance"
    assert enriched["goal"] == "Get a promotion"
    assert enriched["profile"]["department"] == "Finance"


def test_create_hybrid_retriever_course_id_is_vector_only():
    index = MagicMock()
    profile = build_user_profile([], latest_message="Tell me about course 4606")
    filters = build_metadata_filters(profile)
    with patch.object(
        retrieval, "create_vector_retriever", return_value=MagicMock(name="vector")
    ) as vector_mock, patch.object(
        retrieval, "get_base_hybrid_retriever"
    ) as hybrid_mock:
        result = create_hybrid_retriever(index, metadata_filters=filters, profile=profile)
    vector_mock.assert_called_once()
    hybrid_mock.assert_not_called()
    assert result is vector_mock.return_value


def test_create_node_postprocessors_skip_rerank():
    retrieval.clear_bm25_cache()
    with patch.object(retrieval, "_create_reranker") as rerank_mock, patch.object(
        retrieval, "ENABLE_RERANK", True
    ):
        processors = create_node_postprocessors(skip_rerank=True)
    rerank_mock.assert_not_called()
    assert processors  # still has reorder + catalog postprocessor
    retrieval.clear_bm25_cache()


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


def test_extract_course_ids_ignores_years_and_phone_numbers():
    assert extract_course_ids_from_text("Budget courses for 2025 and 2026") == []
    assert extract_course_ids_from_text("Call 888.545.8574 for support") == []
    assert extract_course_ids_from_text("Tell me about course 4606") == ["4606"]
    assert extract_course_ids_from_text("https://www.managementconcepts.com/course/id/4606") == [
        "4606"
    ]


def test_build_metadata_filters_skips_year_like_numbers():
    profile = build_user_profile([], latest_message="What courses are available in 2025?")
    assert build_metadata_filters(profile) is None


def test_metadata_post_filter_retriever_does_not_return_unfiltered_nodes():
    class StubRetriever:
        def retrieve(self, query_bundle):
            return [
                NodeWithScore(
                    node=TextNode(text="Budget course", metadata={"course_id": "4606"}),
                    score=0.9,
                ),
                NodeWithScore(
                    node=TextNode(text="Other course", metadata={"course_id": "9999"}),
                    score=0.8,
                ),
            ]

    filters = build_metadata_filters(
        build_user_profile([], latest_message="Tell me about course 4606")
    )
    retriever = MetadataPostFilterRetriever(StubRetriever(), filters)
    nodes = retriever.retrieve("course 4606")

    assert len(nodes) == 1
    assert nodes[0].node.metadata["course_id"] == "4606"


def test_build_query_expansion_terms():
    profile = build_user_profile(
        [],
        latest_message="My department is: Finance. My career goal is: Get a promotion.",
    )
    terms = build_query_expansion_terms(profile)
    joined = " ".join(terms).lower()
    # Department maps to catalog phrases, not the raw label "Finance".
    assert "financial management" in joined or "budget" in joined
    assert "career advancement" in joined or "promotion" in joined


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
    assert "federal financial management" in StubRetriever.last_query


def test_course_metadata_postprocessor_prepends_structured_header():
    node = TextNode(
        text="Learn data visualization techniques.",
        metadata={
            "course_id": "4606",
            "course_title": "Introduction to Data Visualization",
            "duration": "2 Days",
        },
    )
    processor = CourseMetadataPostprocessor()
    result = processor.postprocess_nodes([NodeWithScore(node=node, score=0.9)])

    content = result[0].node.get_content()
    assert content.startswith(
        "Course ID: 4606 | Title: Introduction to Data Visualization | Duration: 2 Days"
    )
    assert "Learn data visualization techniques." in content


def test_course_metadata_postprocessor_fills_price_from_catalog(tmp_path, monkeypatch):
    from src.ingestion.pricing import clear_price_catalog_cache, save_price_catalog

    monkeypatch.setenv("COURSE_PRICE_CATALOG_PATH", str(tmp_path / "course_prices.json"))
    clear_price_catalog_cache()
    # GSA-derived value is ignored for 4606 when official MC catalog has a price.
    save_price_catalog({"4606": "$14,949.00"})

    node = TextNode(
        text="Learn data visualization techniques.",
        metadata={
            "course_id": "4606",
            "course_title": "Introduction to Data Visualization",
            "duration": "2 Days",
        },
    )
    processor = CourseMetadataPostprocessor()
    result = processor.postprocess_nodes([NodeWithScore(node=node, score=0.9)])

    content = result[0].node.get_content()
    assert "Cost: $1409.00" in content


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