import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import frontmatter

COURSE_ID_PATTERN = re.compile(r"\b(\d{4,6})\b")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_content_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_id_for_path(path: str | Path) -> str:
    normalized = str(Path(path).resolve()).lower().replace("\\", "/")
    return stable_hash(f"path:{normalized}")


def source_id_for_url(url: str) -> str:
    parsed = urlparse(url.strip())
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/").lower()
    return stable_hash(f"url:{normalized}")


def extract_course_ids(text: str) -> list[str]:
    return list(dict.fromkeys(COURSE_ID_PATTERN.findall(text)))


def extract_headings(text: str) -> list[dict[str, Any]]:
    headings = []
    for match in HEADING_PATTERN.finditer(text):
        level = len(match.group(1))
        headings.append({"level": level, "title": match.group(2).strip()})
    return headings


def parse_markdown_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    post = frontmatter.loads(text)
    metadata = dict(post.metadata or {})
    return metadata, post.content


def enrich_document_metadata(
    *,
    text: str,
    source_type: str,
    source_path: str,
    base_metadata: dict[str, Any] | None = None,
    page_label: str | None = None,
    section_title: str | None = None,
) -> dict[str, Any]:
    metadata = dict(base_metadata or {})
    metadata.update(
        {
            "source_type": source_type,
            "source_path": source_path,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    if page_label is not None:
        metadata["page_label"] = page_label
    if section_title:
        metadata["section_title"] = section_title

    course_ids = extract_course_ids(text)
    if course_ids:
        metadata["course_ids"] = course_ids
        if len(course_ids) == 1:
            metadata["course_id"] = course_ids[0]

    headings = extract_headings(text)
    if headings and "section_title" not in metadata:
        metadata["section_title"] = headings[0]["title"]
    if headings:
        metadata["headings"] = headings

    file_name = Path(source_path).name
    metadata.setdefault("file_name", file_name)

    stem_course = re.match(r"^(\d{4,6})", Path(source_path).stem)
    if stem_course:
        metadata.setdefault("course_id", stem_course.group(1))

    return metadata