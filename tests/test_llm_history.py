from unittest.mock import MagicMock, patch

from llama_index.core.llms import ChatMessage, MessageRole

from src.chatbot import chatbot
from src.db.session_manager import get_llm_session_history, should_include_in_llm_history


def test_should_exclude_onboarding_selection():
    assert should_include_in_llm_history(
        "user",
        {"step": "experience", "value": "Entry-level", "type": "onboarding_selection"},
    ) is False


def test_should_exclude_preference_update():
    assert should_include_in_llm_history(
        "user",
        {
            "step": "department",
            "value": "IT",
            "type": "preference_update",
            "visible": False,
        },
    ) is False


def test_should_exclude_hidden_user_message():
    assert should_include_in_llm_history(
        "user",
        {"step": "goal", "value": "Get a promotion", "visible": False},
    ) is False


def test_should_exclude_scripted_onboarding_bot_prompt():
    assert should_include_in_llm_history(
        "assistant",
        {"step": "department", "type": "onboarding", "options": ["Finance"]},
    ) is False


def test_should_include_profile_complete_goal_message():
    assert should_include_in_llm_history(
        "user",
        {
            "step": "goal",
            "profile_complete": True,
            "profile": {"experience": "Entry-level", "department": "Finance", "goal": "Promotion"},
        },
    ) is True


def test_should_include_real_assistant_response():
    assert should_include_in_llm_history("assistant", {"visible": True}) is True


def test_get_llm_session_history_filters_scripted_messages():
    rows = [
        {
            "role": "assistant",
            "content": "Welcome!",
            "metadata": {"step": "welcome", "type": "onboarding"},
        },
        {
            "role": "user",
            "content": "My experience level is: Entry-level.",
            "metadata": {"step": "experience", "type": "onboarding_selection"},
        },
        {
            "role": "user",
            "content": "My career goal is: Promotion. Please recommend courses.",
            "metadata": {"step": "goal", "profile_complete": True},
        },
        {
            "role": "assistant",
            "content": "Here are courses for you.",
            "metadata": None,
        },
    ]
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("src.db.session_manager.get_db_connection", return_value=mock_conn):
        messages = get_llm_session_history("session-1")

    assert len(messages) == 2
    assert messages[0].role == MessageRole.USER
    assert "career goal" in messages[0].content
    assert messages[1].role == MessageRole.ASSISTANT
    assert messages[1].content == "Here are courses for you."


def test_create_chat_engine_skips_condense_for_profile_complete():
    with patch.object(chatbot, "get_index", return_value=MagicMock()), patch.object(
        chatbot, "create_hybrid_retriever", return_value=MagicMock()
    ), patch.object(
        chatbot, "create_node_postprocessors", return_value=[]
    ), patch.object(
        chatbot.CondensePlusContextChatEngine,
        "from_defaults",
        return_value=MagicMock(),
    ) as engine_mock:
        chatbot.create_chat_engine(
            [],
            latest_message="My career goal is: Promotion.",
            request_metadata={"profile_complete": True},
        )

    assert engine_mock.call_args.kwargs["skip_condense"] is True


def test_create_chat_engine_skips_condense_for_free_step_standalone_query():
    with patch.object(chatbot, "get_index", return_value=MagicMock()), patch.object(
        chatbot, "create_hybrid_retriever", return_value=MagicMock()
    ), patch.object(
        chatbot, "create_node_postprocessors", return_value=[]
    ), patch.object(
        chatbot.CondensePlusContextChatEngine,
        "from_defaults",
        return_value=MagicMock(),
    ) as engine_mock:
        chatbot.create_chat_engine(
            [],
            latest_message="Tell me about course 4606",
            request_metadata={"step": "free"},
        )

    assert engine_mock.call_args.kwargs["skip_condense"] is True


def test_create_chat_engine_skips_condense_for_empty_history_without_metadata():
    with patch.object(chatbot, "get_index", return_value=MagicMock()), patch.object(
        chatbot, "create_hybrid_retriever", return_value=MagicMock()
    ), patch.object(
        chatbot, "create_node_postprocessors", return_value=[]
    ), patch.object(
        chatbot.CondensePlusContextChatEngine,
        "from_defaults",
        return_value=MagicMock(),
    ) as engine_mock:
        chatbot.create_chat_engine(
            [],
            latest_message="What budgeting courses do you offer?",
            request_metadata=None,
        )

    assert engine_mock.call_args.kwargs["skip_condense"] is True


def test_get_or_create_chat_engine_reuses_cached_session_engine():
    chatbot.clear_session_engine_cache()
    fake_engine = MagicMock()
    fake_engine._skip_condense = False
    fake_engine._memory = object()
    fake_engine._retriever = MagicMock()

    with patch.object(chatbot, "create_chat_engine", return_value=fake_engine) as create_mock, patch.object(
        chatbot, "_memory_from_history", return_value=MagicMock()
    ) as memory_mock, patch.object(
        chatbot, "create_hybrid_retriever", return_value=MagicMock()
    ):
        first = chatbot.get_or_create_chat_engine(
            "session-a",
            [ChatMessage(role=MessageRole.USER, content="hello")],
            latest_message="hello",
        )
        second = chatbot.get_or_create_chat_engine(
            "session-a",
            [
                ChatMessage(role=MessageRole.USER, content="hello"),
                ChatMessage(role=MessageRole.ASSISTANT, content="hi"),
            ],
            latest_message="follow up",
        )

    assert first is second
    create_mock.assert_called_once()
    memory_mock.assert_called()
    chatbot.clear_session_engine_cache()