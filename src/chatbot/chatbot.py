import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from src.chatbot.query_context import build_metadata_filters, build_user_profile
from src.ingestion.vector_store import load_index as load_vector_index
from src.chatbot.retrieval import (
    build_condense_prompt,
    create_hybrid_retriever,
    create_node_postprocessors,
    initialize_retrieval,
)
logger = logging.getLogger(__name__)

load_dotenv()

SYSTEM_PROMPT = """You are Course Advisor for Management Concepts — a concise, friendly assistant for course discovery.

Scope: Use only the provided catalog context for course discovery, recommendations, duration, cost, level, and delivery questions. Never invent courses.

Catalog-only rules (strict):
- Only recommend courses that appear in the provided context WITH a concrete Course ID.
- Never mention programs, packages, or course names that lack a Course ID in context.
- Use Title, Duration, Level, and Cost from the context header exactly — do not invent or alter them.
- Prefer core department training (e.g. Finance → financial management / budget / accounting) over coaching, accelerators, or loosely related topics unless the learner asks for those.
- Match Experience Level: entry → foundational/overview/basic; mid → intermediate/applied; senior → advanced/leadership.
- If the user asks about something outside Management Concepts training (cooking, sports, weather, general trivia, etc.), do NOT list courses. Reply briefly that you only help with Management Concepts courses and invite a training-related question.

Pricing: When Cost appears in the context header, include it on that course. If Cost is absent from the header, omit the Cost line (do not guess). Never invent prices.

Out-of-scope / non-course issues — never invent troubleshooting and never send the learner to another page.
For password, login, account, billing, site, agent, or other technical support needs, use this contact message (or close paraphrase):
"Please contact our technical support team at 844-876-7476, via email (technicalsupport@managementconcepts.com), or select Speak with Agent below and we'll connect you."
For certificate print/generate/download: acknowledge the request was received and will be generated shortly; include the same phone/email if helpful.

If nothing in the catalog matches a course question, briefly say you help with Management Concepts courses and suggest a related search (budgeting, project management, leadership, etc.). Never say "Information not available." Never return an empty response. Do not pad with unrelated course cards.

Accuracy: Each context block may begin with a metadata header (Course ID, Title, Duration, Level, Cost, Delivery). Use those values exactly — never invent or swap course IDs, titles, durations, levels, or prices.

Style: Warm but brief. Skip greetings after the first turn. Lead with the answer; add at most 1–2 short sentences of context. One line per course on why it fits. No filler, repetition, or long intros.

Lists: Use Markdown bullets (- ) or numbered lists (1. ) — never plain indented lines.

Course format (required for each course — title is plain text, not a hyperlink):
**[COURSE_ID] — [Course Title]**
Duration: ... (only if present in context)
Level: ... (only if present in context)
Cost: ... (only if present in context)
Description: ...

Do not wrap the course title in a markdown link. A Register Now link is added automatically — do not invent extra product links.

Recommend 3–5 courses unless asked for more. Tailor picks to Experience Level, Department, and Career Goal when provided in the message."""

CHAT_MEMORY_TOKEN_LIMIT = int(os.getenv("CHAT_MEMORY_TOKEN_LIMIT", "3000"))
SESSION_ENGINE_TTL_SECONDS = int(os.getenv("SESSION_ENGINE_TTL_SECONDS", "1800"))
SESSION_ENGINE_CACHE_MAX_SIZE = int(os.getenv("SESSION_ENGINE_CACHE_MAX_SIZE", "200"))


@dataclass
class _CachedSessionEngine:
    engine: CondensePlusContextChatEngine
    profile_key: str
    updated_at: float


_session_engine_cache: dict[str, _CachedSessionEngine] = {}


def load_index() -> VectorStoreIndex:
    """Loads the index from PostgreSQL vector store (Supabase or local via vector_config)."""
    try:
        from src.db.connection import db_label

        print(f"Using {db_label()} vector store...")
        return load_vector_index()
    except Exception as e:
        logger.error(f"Error loading index: {e}")
        raise


_index = None
_index_lock = threading.Lock()


def get_index() -> VectorStoreIndex:
    """Return the shared vector index, loading it on first use."""
    global _index
    if _index is None:
        with _index_lock:
            if _index is None:
                from src.config import configure_llama_index

                configure_llama_index()
                _index = load_index()
    return _index


def init_chatbot() -> VectorStoreIndex:
    """Eagerly load the index and pre-warm retrieval. Call from app startup."""
    idx = get_index()
    try:
        initialize_retrieval(idx)
        logger.info("Retrieval stack pre-warmed (BM25 + reranker).")
    except Exception as exc:
        logger.warning("Retrieval pre-warm failed; will retry on first chat: %s", exc)
    return idx


def _should_skip_condense(
    request_metadata: dict[str, Any] | None,
    chat_history: list | None = None,
) -> bool:
    """Skip query condensation to cut latency (extra LLM round-trip) when safe.

    Default is skip. Only condense short follow-ups that likely refer to prior turns
    (e.g. "those", "the first one") when history exists.
    """
    if os.getenv("CHAT_SKIP_CONDENSE", "true").lower() in ("1", "true", "yes"):
        return True

    if not request_metadata:
        return not chat_history

    if request_metadata.get("profile_complete"):
        return True

    if request_metadata.get("step") in ("free", "goal", "experience", "department"):
        return True

    return not chat_history


def _memory_from_history(chat_history: list) -> ChatMemoryBuffer:
    return ChatMemoryBuffer.from_defaults(
        chat_history=chat_history,
        token_limit=CHAT_MEMORY_TOKEN_LIMIT,
    )


def _prune_session_engine_cache() -> None:
    now = time.time()
    expired = [
        sid
        for sid, entry in _session_engine_cache.items()
        if now - entry.updated_at > SESSION_ENGINE_TTL_SECONDS
    ]
    for sid in expired:
        _session_engine_cache.pop(sid, None)

    overflow = len(_session_engine_cache) - SESSION_ENGINE_CACHE_MAX_SIZE
    if overflow > 0:
        oldest = sorted(
            _session_engine_cache.items(),
            key=lambda item: item[1].updated_at,
        )[:overflow]
        for sid, _ in oldest:
            _session_engine_cache.pop(sid, None)


def clear_session_engine_cache(session_id: str | None = None) -> None:
    if session_id is None:
        _session_engine_cache.clear()
    else:
        _session_engine_cache.pop(session_id, None)


def create_chat_engine(
    chat_history=None,
    *,
    latest_message: str | None = None,
    request_metadata: dict[str, Any] | None = None,
    skip_condense: bool | None = None,
):
    """
    Creates a chat engine with hybrid retrieval, reranking, query expansion,
    metadata filtering, and context compression.
    """
    if chat_history is None:
        chat_history = []

    if skip_condense is None:
        skip_condense = _should_skip_condense(request_metadata, chat_history)

    profile = build_user_profile(
        chat_history,
        latest_message=latest_message,
        request_metadata=request_metadata,
    )
    metadata_filters = build_metadata_filters(profile)
    retriever = create_hybrid_retriever(
        get_index(),
        metadata_filters=metadata_filters,
        profile=profile,
    )

    memory = _memory_from_history(chat_history)

    return CondensePlusContextChatEngine.from_defaults(
        retriever=retriever,
        memory=memory,
        system_prompt=SYSTEM_PROMPT,
        condense_prompt=build_condense_prompt(profile),
        node_postprocessors=create_node_postprocessors(),
        skip_condense=skip_condense,
        verbose=os.getenv("CHAT_VERBOSE", "false").lower() == "true",
    )


def get_or_create_chat_engine(
    session_id: str,
    chat_history=None,
    *,
    latest_message: str | None = None,
    request_metadata: dict[str, Any] | None = None,
):
    """Return a cached chat engine for the session, refreshing memory and retriever as needed."""
    if chat_history is None:
        chat_history = []

    skip_condense = _should_skip_condense(request_metadata, chat_history)
    profile = build_user_profile(
        chat_history,
        latest_message=latest_message,
        request_metadata=request_metadata,
    )
    profile_key = profile.summary()
    now = time.time()

    _prune_session_engine_cache()

    cached = _session_engine_cache.get(session_id)
    if cached and now - cached.updated_at <= SESSION_ENGINE_TTL_SECONDS:
        engine = cached.engine
        engine._skip_condense = skip_condense
        engine._memory = _memory_from_history(chat_history)
        if cached.profile_key != profile_key:
            metadata_filters = build_metadata_filters(profile)
            engine._retriever = create_hybrid_retriever(
                get_index(),
                metadata_filters=metadata_filters,
                profile=profile,
            )
            cached.profile_key = profile_key
        cached.updated_at = now
        return engine

    engine = create_chat_engine(
        chat_history,
        latest_message=latest_message,
        request_metadata=request_metadata,
        skip_condense=skip_condense,
    )
    _session_engine_cache[session_id] = _CachedSessionEngine(
        engine=engine,
        profile_key=profile_key,
        updated_at=now,
    )
    _prune_session_engine_cache()
    return engine


def get_streaming_response(chat_engine, user_message: str):
    """
    Returns a raw streaming response object.
    Post-processing (e.g. Register Now link injection) is handled by the caller (main.py)
    after buffering the full response text.
    """
    return chat_engine.stream_chat(user_message)