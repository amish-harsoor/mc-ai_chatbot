"""Shared course card markdown — one clean CTA, no duplicate hyperlinks."""

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
    level: str | None = None,
    price: str | None = None,
    credits: str | None = None,
    description: str | None = None,
    why: str | None = None,
    extra_lines: list[str] | None = None,
) -> str:
    """
    Clean learner-facing course block:

      **4606 — Course Title**
      Duration: …
      Level: …
      Cost: …
      Description: …
      [Register Now](url)

    Title is plain bold text (not a link). Single register CTA only.
    """
    cid = str(course_id).strip()
    display_title = (title or f"Course {cid}").strip()
    link = product_url(cid, url)

    lines = [f"**{cid} — {display_title}**"]
    if duration:
        lines.append(f"Duration: {duration}")
    if level:
        lines.append(f"Level: {level}")
    if price:
        lines.append(f"Cost: {price}")
    if credits:
        lines.append(f"Credits: {credits}")
    if description:
        lines.append(f"Description: {description}")
    if why:
        lines.append(why)
    if extra_lines:
        lines.extend(extra_lines)
    lines.append(f"[Register Now]({link})")
    return "\n".join(lines)


def format_course_card_from_metadata(
    metadata: dict[str, Any],
    *,
    description: str | None = None,
    why: str | None = None,
    include_credits: bool = False,
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
        level=metadata.get("level"),
        price=metadata.get("price"),
        credits=metadata.get("credits") if include_credits else None,
        description=description,
        why=why,
    )


# --- Stream post-processing (LLM + any leftover dual-link shapes) ---

# [Title](https://www.managementconcepts.com/product/1234) → Title
_PRODUCT_MD_LINK_RE = re.compile(
    r"\[([^\]]+)\]\(https?://(?:www\.)?managementconcepts\.com/product/(\d+)/?\)",
    re.IGNORECASE,
)

# **4606** or **4606 — Title** (title may already be plain)
_COURSE_HEADER_RE = re.compile(
    r"\*\*(\d{4,6})(?:\s*[—–-]\s*[^*]+)?\*\*",
)

# Already has Register Now for this id nearby
_REGISTER_NEAR_RE = re.compile(
    r"\[Register Now\]\(https?://(?:www\.)?managementconcepts\.com/product/(\d+)/?\)",
    re.IGNORECASE,
)


def normalize_course_markdown(text: str) -> str:
    """
    Clean streamed course markdown for display:

    1. Convert product title hyperlinks to plain text (avoid dual links).
    2. Ensure each course block has exactly one Register Now (if missing).
    """
    if not text:
        return text

    # Keep Register Now labels; plain-out other product markdown links (titles).
    def _demote_product_links(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        if label.lower() == "register now":
            return match.group(0)
        return label

    cleaned = _PRODUCT_MD_LINK_RE.sub(_demote_product_links, text)
    headers = list(_COURSE_HEADER_RE.finditer(cleaned))
    if not headers:
        return cleaned

    # Insert Register Now only when missing between this header and the next.
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
