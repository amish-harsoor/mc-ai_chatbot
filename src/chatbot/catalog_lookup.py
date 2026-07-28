"""Zero-LLM answers for fact questions about a known course ID.

Uses the official catalog JSON (and price fallback) — no RAG, no generation.
"""

from __future__ import annotations

import os
import re
from typing import Any, Literal

from src.chatbot.course_cards import format_course_card_markdown, product_url
from src.chatbot.query_context import YEAR_LIKE_ID_PATTERN, extract_course_ids_from_text
from src.ingestion.course_catalog import get_course

# CHAT_CATALOG_LOOKUP=false disables this short-circuit (fall through to RAG/LLM).
_LOOKUP_ENABLED = os.getenv("CHAT_CATALOG_LOOKUP", "true").lower() in (
    "1",
    "true",
    "yes",
)
_MAX_COURSES = 3

FactField = Literal["cost", "duration", "level", "credits", "title", "url", "overview"]

# product/4606, /product/4606 — common when pasting MC links
_PRODUCT_URL_ID_RE = re.compile(
    r"(?:managementconcepts\.com/)?product/(\d{4,6})\b",
    re.IGNORECASE,
)
# Bare 4–6 digit id only when the message is clearly a fact question
_BARE_ID_RE = re.compile(r"\b(\d{4,6})\b")

_FIELD_PATTERNS: list[tuple[FactField, re.Pattern[str]]] = [
    (
        "cost",
        re.compile(
            r"\b(cost|price|tuition|fee|how much|pricing|\$)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "duration",
        re.compile(
            r"\b(duration|how long|length|how many days)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "level",
        re.compile(
            r"\b(level|difficulty|experience level|what level)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "credits",
        re.compile(r"\b(credits?|clp|cpe|ceu)\b", re.IGNORECASE),
    ),
    (
        "title",
        re.compile(r"\b(title|name of (the )?course|called)\b", re.IGNORECASE),
    ),
    (
        "url",
        re.compile(
            r"\b(url|link|register|sign ?up|enroll(ment)?|webpage|web page)\b",
            re.IGNORECASE,
        ),
    ),
]

# "tell me about course X", "details on 4606", bare overview
_OVERVIEW_PATTERNS = [
    re.compile(
        r"\b(tell me about|what is|what'?s|info(rmation)? (on|about)|details? (on|for|about)|"
        r"look up|lookup|show me|describe)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(course|class|training)\s+(?:id\s+|number\s*:?\s*|#)?\d{4,6}\b",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*(?:course\s+)?#?\d{4,6}\s*[?.!]?\s*$", re.IGNORECASE),
]

# Open discovery — leave for RAG/LLM (or profile template), not fact lookup
_DISCOVERY_RE = re.compile(
    r"\b(recommend|recommendation|suggest|suggestions?|looking for|"
    r"what (courses|classes|training)|which courses|list (of )?(courses|classes)|"
    r"based on my profile|please recommend)\b",
    re.IGNORECASE,
)


def catalog_lookup_enabled() -> bool:
    return _LOOKUP_ENABLED


def extract_lookup_course_ids(message: str) -> list[str]:
    """Course IDs for fact lookup: structured refs, product URLs, then bare ids."""
    text = message or ""
    ids = list(extract_course_ids_from_text(text))
    for match in _PRODUCT_URL_ID_RE.findall(text):
        if match and not YEAR_LIKE_ID_PATTERN.match(match):
            ids.append(match)

    # Bare numeric ids only when message already looks like a fact/overview ask
    # or already has at least one structured id context word.
    if not ids and _looks_like_fact_or_overview(text):
        for match in _BARE_ID_RE.findall(text):
            if match and not YEAR_LIKE_ID_PATTERN.match(match):
                ids.append(match)

    # Dedupe preserve order
    return list(dict.fromkeys(ids))


def _looks_like_fact_or_overview(text: str) -> bool:
    if any(pat.search(text) for _, pat in _FIELD_PATTERNS):
        return True
    return any(pat.search(text) for pat in _OVERVIEW_PATTERNS)


def detect_requested_fields(message: str) -> list[FactField]:
    """Which catalog fields the user is asking about (empty → full overview)."""
    text = message or ""
    fields: list[FactField] = []
    for field, pattern in _FIELD_PATTERNS:
        if pattern.search(text):
            fields.append(field)
    return fields


def should_use_catalog_lookup(
    message: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """True when this turn should answer from catalog JSON only."""
    if not catalog_lookup_enabled():
        return False
    if not message or not str(message).strip():
        return False

    meta = metadata or {}
    # Structured profile recs stay on the template recommendation path.
    if meta.get("profile_complete") is True or meta.get("step") == "goal":
        return False

    text = str(message).strip()
    if _DISCOVERY_RE.search(text):
        return False

    ids = extract_lookup_course_ids(text)
    if not ids or len(ids) > _MAX_COURSES:
        return False

    return _looks_like_fact_or_overview(text)


def _resolve_course_entry(course_id: str) -> dict[str, Any] | None:
    entry = get_course(course_id)
    if not entry:
        return None
    out = dict(entry)
    # Price fallback from shared price catalog when official entry has none
    if not out.get("price"):
        try:
            from src.ingestion.pricing import lookup_course_price

            price = lookup_course_price(course_id)
            if price:
                out["price"] = price
        except Exception:
            pass
    if not out.get("url"):
        out["url"] = product_url(course_id)
    return out


def _missing_field_note(field: FactField) -> str | None:
    labels = {
        "cost": "Cost: not listed in the catalog for this course.",
        "duration": "Duration: not listed in the catalog for this course.",
        "level": "Level: not listed in the catalog for this course.",
        "credits": "Credits: not listed in the catalog for this course.",
        "title": "Title: not listed in the catalog for this course.",
    }
    return labels.get(field)


def format_course_fact_card(
    entry: dict[str, Any],
    *,
    fields: list[FactField] | None = None,
) -> str:
    """Clean card from official catalog fields — plain title, one Register Now CTA."""
    course_id = str(entry.get("course_id") or "").strip()
    title = (entry.get("title") or entry.get("course_title") or f"Course {course_id}").strip()
    url = entry.get("url") or product_url(course_id)

    requested = [f for f in (fields or []) if f not in ("overview", "url", "title")]
    extra: list[str] = []

    # If user asked for a field that is missing, note it explicitly once.
    if requested:
        for field in requested:
            if field == "cost" and not entry.get("price"):
                note = _missing_field_note("cost")
                if note:
                    extra.append(note)
            elif field == "duration" and not entry.get("duration"):
                note = _missing_field_note("duration")
                if note:
                    extra.append(note)
            elif field == "level" and not entry.get("level"):
                note = _missing_field_note("level")
                if note:
                    extra.append(note)
            elif field == "credits" and not entry.get("credits"):
                note = _missing_field_note("credits")
                if note:
                    extra.append(note)

    return format_course_card_markdown(
        course_id=course_id,
        title=title,
        url=url,
        duration=entry.get("duration"),
        credits=entry.get("credits"),
        price=entry.get("price"),
        extra_lines=extra or None,
    )


def build_catalog_lookup_reply(message: str) -> str | None:
    """
    Build a fixed catalog reply for a fact-lookup message.

    Returns None when the message should not use this path (caller continues).
    """
    if not should_use_catalog_lookup(message):
        return None

    ids = extract_lookup_course_ids(message)
    if not ids:
        return None

    fields = detect_requested_fields(message)
    cards: list[str] = []
    missing: list[str] = []

    for course_id in ids[:_MAX_COURSES]:
        entry = _resolve_course_entry(course_id)
        if not entry:
            missing.append(course_id)
            continue
        cards.append(format_course_fact_card(entry, fields=fields))

    if not cards and missing:
        missing_list = ", ".join(missing)
        return (
            f"I couldn't find course ID{'s' if len(missing) > 1 else ''} "
            f"{missing_list} in the Management Concepts catalog. "
            "Double-check the number, or ask about a topic (budgeting, leadership, "
            "project management) and I can recommend courses."
        )

    parts: list[str] = []
    if len(cards) == 1 and fields and "cost" in fields and len(fields) == 1:
        parts.append("Here's the catalog pricing for that course:")
    elif len(cards) == 1 and fields and len(fields) == 1:
        parts.append("Here's what the catalog has for that course:")
    elif len(cards) == 1:
        parts.append("Here's the catalog entry for that course:")
    else:
        parts.append("Here's what the catalog has for those courses:")

    parts.append("")
    parts.append("\n\n".join(cards))

    if missing:
        parts.append("")
        parts.append(
            "I couldn't find course ID"
            f"{'s' if len(missing) > 1 else ''} {', '.join(missing)} in the catalog."
        )

    return "\n".join(parts).strip()
