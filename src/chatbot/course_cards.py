"""Shared course card markdown — concise facts + single Register Now CTA."""

from __future__ import annotations

import re
from typing import Any


def product_url(course_id: str, url: str | None = None) -> str:
    cleaned = (url or "").strip()
    if cleaned:
        return cleaned
    return f"https://www.managementconcepts.com/product/{course_id}"


def format_course_card_markdown(
    *,
    course_id: str,
    title: str,
    url: str | None = None,
    duration: str | None = None,
    credits: str | None = None,
    price: str | None = None,
    description: str | None = None,  # ignored — layout is title + facts only
    why: str | None = None,  # ignored
    level: str | None = None,  # ignored
    extra_lines: list[str] | None = None,
) -> str:
    """
    Concise learner-facing course block.

    Uses blank lines between rows so Markdown renders each fact on its own line
    (single newlines collapse into one paragraph in CommonMark/GFM).

      **Course Title**

      Duration: …

      Credits: …

      Cost: …

      [Register Now](url)
    """
    del description, why, level
    cid = str(course_id).strip()
    display_title = (title or f"Course {cid}").strip()
    link = product_url(cid, url)

    parts = [f"**{display_title}**"]
    if duration:
        parts.append(f"**Duration:** {duration}")
    if credits:
        parts.append(f"**Credits:** {credits}")
    if price:
        parts.append(f"**Cost:** {price}")
    if extra_lines:
        for line in extra_lines:
            if isinstance(line, str):
                line = re.sub(
                    r"^(Duration|Credits|Cost|Level):",
                    r"**\1:**",
                    line,
                    count=1,
                )
            parts.append(line)
    parts.append(f"[Register Now]({link})")
    # Double newlines → separate <p> tags in the chat markdown renderer
    return "\n\n".join(parts)


def format_course_card_from_metadata(
    metadata: dict[str, Any],
    *,
    description: str | None = None,
    why: str | None = None,
    include_credits: bool = True,
) -> str | None:
    course_id = str(metadata.get("course_id") or "").strip()
    if not course_id:
        return None
    title = (
        metadata.get("course_title")
        or metadata.get("title")
        or f"Course {course_id}"
    )
    return format_course_card_markdown(
        course_id=course_id,
        title=str(title).strip(),
        url=metadata.get("url"),
        duration=metadata.get("duration"),
        credits=metadata.get("credits") if include_credits else None,
        price=metadata.get("price"),
        description=description,
        why=why,
    )


# --- Stream post-processing (LLM + any leftover dual-link shapes) ---

_PRODUCT_MD_LINK_RE = re.compile(
    r"\[([^\]]+)\]\(https?://(?:www\.)?managementconcepts\.com/product/(\d+)/?\)",
    re.IGNORECASE,
)

_COURSE_ID_HEADER_RE = re.compile(
    r"\*\*(\d{4,6})(?:\s*[—–-]\s*[^*]+)?\*\*",
)

_REGISTER_NEAR_RE = re.compile(
    r"\[Register Now\]\(https?://(?:www\.)?managementconcepts\.com/product/(\d+)/?\)",
    re.IGNORECASE,
)


def normalize_course_markdown(text: str) -> str:
    """
    Clean streamed course markdown for display:

    1. Convert product title hyperlinks to plain text (avoid dual links).
    2. For legacy **course_id** headers, ensure a Register Now CTA exists.
    """
    if not text:
        return text

    def _demote_product_links(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        if label.lower() == "register now":
            return match.group(0)
        return label

    cleaned = _PRODUCT_MD_LINK_RE.sub(_demote_product_links, text)
    headers = list(_COURSE_ID_HEADER_RE.finditer(cleaned))
    if not headers:
        return cleaned

    inserts: list[tuple[int, str]] = []
    for i, match in enumerate(headers):
        course_id = match.group(1)
        block_start = match.end()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(cleaned)
        block = cleaned[block_start:block_end]
        has_register = any(
            reg.group(1) == course_id for reg in _REGISTER_NEAR_RE.finditer(block)
        )
        if not has_register:
            inserts.append(
                (block_start, f"\n[Register Now]({product_url(course_id)})")
            )

    if not inserts:
        return cleaned

    parts: list[str] = []
    cursor = 0
    for pos, snippet in inserts:
        parts.append(cleaned[cursor:pos])
        parts.append(snippet)
        cursor = pos
    parts.append(cleaned[cursor:])
    return "".join(parts)
