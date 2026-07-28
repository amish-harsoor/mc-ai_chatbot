"""Deterministic course recommendations for structured profile turns (no LLM).

Used when onboarding completes (or a goal chip refresh) so ranking still comes
from hybrid retrieval + catalog metadata, while the reply is templated.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from llama_index.core.schema import NodeWithScore, QueryBundle

from src.chatbot.course_cards import format_course_card_from_metadata
from src.chatbot.query_context import UserProfile, build_user_profile
from src.ingestion.course_catalog import apply_official_catalog, get_course

logger = logging.getLogger(__name__)

# Keep template recs on by default; set CHAT_TEMPLATE_PROFILE_RECS=false to force LLM.
_TEMPLATE_ENABLED = os.getenv("CHAT_TEMPLATE_PROFILE_RECS", "true").lower() in (
    "1",
    "true",
    "yes",
)
_MAX_COURSES = int(os.getenv("CHAT_TEMPLATE_RECS_MAX", "5"))
_MIN_COURSES = 1
_DESCRIPTION_MAX_CHARS = 220

_HEADER_LINE_RE = re.compile(
    r"^Course ID:\s*.+?(?:\s*\|\s*.+)*\s*$",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def template_profile_recs_enabled() -> bool:
    return _TEMPLATE_ENABLED


def should_use_template_recommendations(
    request_metadata: dict[str, Any] | None,
) -> bool:
    """True for structured profile-complete recommendation turns only."""
    if not template_profile_recs_enabled():
        return False
    meta = request_metadata or {}
    if meta.get("profile_complete") is True:
        return True
    # Goal step with a full profile payload (frontend always sends profile_complete,
    # but accept step+profile as a safe fallback).
    if meta.get("step") == "goal":
        profile = meta.get("profile")
        if isinstance(profile, dict) and all(
            profile.get(k) for k in ("experience", "department", "goal")
        ):
            return True
    return False


def build_profile_search_query(profile: UserProfile) -> str:
    """Build a retrieval query from structured prefs (no chat history needed)."""
    parts: list[str] = []
    if profile.department:
        parts.append(f"{profile.department} training courses")
    if profile.experience:
        parts.append(f"{profile.experience} experience")
    if profile.goal:
        parts.append(f"career goal {profile.goal}")
    if not parts:
        parts.append("Management Concepts course recommendations")
    parts.append("recommend core catalog courses")
    return " ".join(parts)


def _official_metadata(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Apply the same official catalog overlay used in RAG postprocessing."""
    metadata = dict(raw or {})
    metadata = apply_official_catalog(metadata)
    # Prefer full official entry when present so title/duration/level/price are canonical.
    course_id = metadata.get("course_id")
    if course_id:
        entry = get_course(course_id)
        if entry:
            if entry.get("title"):
                metadata["course_title"] = entry["title"]
                metadata["title"] = entry["title"]
            for key in ("duration", "level", "credits", "url", "price"):
                if entry.get(key):
                    metadata[key] = entry[key]
    # Price fill from price catalog when still missing (same as CourseMetadataPostprocessor).
    try:
        from src.ingestion.pricing import apply_catalog_prices

        metadata = apply_catalog_prices(metadata)
    except Exception:
        pass
    return metadata


def _extract_description(node_text: str, metadata: dict[str, Any]) -> str:
    """Short description from chunk body; never invent course facts."""
    text = (node_text or "").strip()
    if not text:
        return "Catalog course matching your profile."

    lines = text.splitlines()
    body_lines: list[str] = []
    for i, line in enumerate(lines):
        if i == 0 and _HEADER_LINE_RE.match(line.strip()):
            continue
        body_lines.append(line)
    body = _WHITESPACE_RE.sub(" ", "\n".join(body_lines)).strip()

    # Drop repeated title-only lead-ins
    title = (metadata.get("course_title") or metadata.get("title") or "").strip()
    if title and body.lower().startswith(title.lower()):
        body = body[len(title) :].lstrip(" :-–—|")

    if not body:
        return "Catalog course matching your profile."

    if len(body) <= _DESCRIPTION_MAX_CHARS:
        return body

    cut = body[:_DESCRIPTION_MAX_CHARS]
    # Prefer sentence or word boundary
    for sep in (". ", "; ", ", "):
        idx = cut.rfind(sep)
        if idx >= 80:
            return cut[: idx + 1].strip()
    sp = cut.rfind(" ")
    if sp > 80:
        return cut[:sp].rstrip() + "…"
    return cut.rstrip() + "…"


def _why_line(profile: UserProfile) -> str:
    bits: list[str] = []
    if profile.department:
        bits.append(f"your {profile.department} focus")
    if profile.experience:
        bits.append(f"{profile.experience} experience")
    if profile.goal:
        bits.append(f"goal: {profile.goal}")
    if not bits:
        return "Strong fit based on your profile."
    return "Fits " + ", ".join(bits) + "."


def format_course_card(
    metadata: dict[str, Any],
    *,
    description: str,
    why: str | None = None,
) -> str | None:
    """Render one course card: plain title + single Register Now CTA."""
    return format_course_card_from_metadata(
        metadata,
        description=description,
        why=why,
    )


def nodes_to_course_cards(
    nodes: list[NodeWithScore],
    profile: UserProfile,
    *,
    max_courses: int | None = None,
) -> list[str]:
    """Dedupe by course_id, apply official catalog fields, format cards."""
    limit = max_courses if max_courses is not None else _MAX_COURSES
    why = _why_line(profile)
    cards: list[str] = []
    seen: set[str] = set()

    for node_with_score in nodes:
        raw_meta = dict(node_with_score.node.metadata or {})
        metadata = _official_metadata(raw_meta)
        course_id = str(metadata.get("course_id") or "").strip()
        if not course_id or course_id in seen:
            continue
        seen.add(course_id)

        description = _extract_description(
            node_with_score.node.get_content(),
            metadata,
        )
        card = format_course_card(metadata, description=description, why=why)
        if card:
            cards.append(card)
        if len(cards) >= limit:
            break
    return cards


def build_intro(profile: UserProfile) -> str:
    focus = []
    if profile.department:
        focus.append(profile.department)
    if profile.experience:
        focus.append(profile.experience)
    if profile.goal:
        focus.append(profile.goal)
    if focus:
        return (
            "Based on your profile ("
            + " · ".join(focus)
            + "), here are courses from the Management Concepts catalog:"
        )
    return "Here are courses from the Management Concepts catalog that match your profile:"


def build_empty_reply(profile: UserProfile) -> str:
    dept = profile.department or "your area"
    return (
        f"I couldn't find a strong catalog match for {dept} just now. "
        "Try a follow-up with topics like budgeting, project management, "
        "leadership, or a specific course ID."
    )


def retrieve_recommendation_nodes(
    profile: UserProfile,
    *,
    query: str | None = None,
) -> list[NodeWithScore]:
    """Run the same hybrid retrieve + postprocess stack as the chat engine."""
    from src.chatbot.chatbot import get_index
    from src.chatbot.query_context import build_metadata_filters
    from src.chatbot.retrieval import create_hybrid_retriever, create_node_postprocessors

    search_query = query or build_profile_search_query(profile)
    metadata_filters = build_metadata_filters(profile)
    retriever = create_hybrid_retriever(
        get_index(),
        metadata_filters=metadata_filters,
        profile=profile,
    )
    nodes = retriever.retrieve(search_query)
    query_bundle = QueryBundle(query_str=search_query)
    for postprocessor in create_node_postprocessors():
        nodes = postprocessor.postprocess_nodes(nodes, query_bundle=query_bundle)
    return nodes


def build_template_recommendation_reply(
    *,
    latest_message: str | None = None,
    request_metadata: dict[str, Any] | None = None,
    chat_history: list | None = None,
) -> str:
    """Full no-LLM recommendation reply for a profile-complete turn."""
    profile = build_user_profile(
        chat_history,
        latest_message=latest_message,
        request_metadata=request_metadata,
    )
    try:
        nodes = retrieve_recommendation_nodes(profile)
    except Exception as exc:
        logger.error("Template recommendation retrieval failed: %s", exc, exc_info=True)
        raise

    cards = nodes_to_course_cards(nodes, profile)
    if len(cards) < _MIN_COURSES:
        return build_empty_reply(profile)

    return build_intro(profile) + "\n\n" + "\n\n".join(cards)
