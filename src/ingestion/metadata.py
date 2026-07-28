import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import frontmatter

COURSE_NUMBER_PATTERN = re.compile(r"Course\s+Number:\s*(\d{4,6})\b", re.IGNORECASE)
COURSE_URL_PATTERN = re.compile(r"course/id/(\d{4,6})\b", re.IGNORECASE)
# PDFs often wrap titles across 1–3 lines immediately above "Course Number:"
COURSE_TITLE_BEFORE_NUMBER_PATTERN = re.compile(
    r"(?:^|\n)\s*((?:[^\n]{2,120}\n){0,3}[^\n]{2,120}?)\s*\n\s*Course\s+Number:\s*\d{4,6}",
    re.IGNORECASE,
)
COURSE_HEADER_TITLE_PATTERN = re.compile(
    r"Management Concepts\s*\n\s*((?:[^\n]{2,120}\n){0,2}[^\n]{2,120}?)\s*\n\s*"
    r"(?:Course\s+(?:Number|Schedule|Description)|Professional|Credits|Ready to Enroll)",
    re.IGNORECASE,
)
_TITLE_NOISE_LINE = re.compile(
    r"(?i)^("
    r"888[\d.\s-]*|©|copyright|management\s*concepts\.com|www\.|"
    r"length:|primary delivery|alternative delivery|course description|"
    r"intended audience|course learning|ready to enroll|credits?"
    r").*"
)
_WEAK_TITLE_WORDS = frozenset(
    {
        "managers",
        "management",
        "budgets",
        "budget",
        "assurance",
        "requirements",
        "self guided",
        "self-guided",
        "programs",
        "program",
        "workshop",
        "professionals",
        "analysis",
        "standards",
        "personnel",
        "environment",
        "leaders",
        "excel",
        "applications",
        "relationships",
        "recipients",
        "leases",
        "fraud",
        "preparation course",
    }
)
LENGTH_PATTERN = re.compile(r"Length:\s*(.+?)(?:\n|$)", re.IGNORECASE)
PRICE_PATTERN = re.compile(
    r"(?:Price|Cost|Tuition|Fee)s?:\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)
DELIVERY_PATTERN = re.compile(
    r"Primary Delivery Method:\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

COURSE_METADATA_KEYS = (
    "course_id",
    "course_title",
    "duration",
    "price",
    "delivery_method",
    "department",
)


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


def _course_id_from_path(source_path: str) -> str | None:
    stem_course = re.match(r"^(\d{4,6})", Path(source_path).stem)
    if stem_course:
        return stem_course.group(1)
    return None


def extract_course_ids(text: str, *, source_path: str | None = None) -> list[str]:
    """Collect course IDs from explicit catalog markers only (not phone numbers or years)."""
    ids: list[str] = []
    ids.extend(COURSE_NUMBER_PATTERN.findall(text))
    ids.extend(COURSE_URL_PATTERN.findall(text))

    if source_path:
        path_id = _course_id_from_path(source_path)
        if path_id:
            ids.append(path_id)

    return list(dict.fromkeys(ids))


def extract_primary_course_id(text: str, *, source_path: str) -> str | None:
    """Resolve the canonical course ID for a document."""
    number_match = COURSE_NUMBER_PATTERN.search(text)
    if number_match:
        return number_match.group(1)

    url_match = COURSE_URL_PATTERN.search(text)
    if url_match:
        return url_match.group(1)

    return _course_id_from_path(source_path)


def _normalize_title_candidate(raw: str) -> str | None:
    """Join wrapped PDF title lines and drop footer/header noise."""
    if not raw:
        return None
    lines: list[str] = []
    for line in re.split(r"[\r\n]+", raw):
        cleaned = re.sub(r"\s+", " ", line).strip(" \t-|•·")
        # Strip markdown heading markers from title lines
        cleaned = re.sub(r"^#{1,6}\s*", "", cleaned).strip()
        if not cleaned:
            continue
        if _TITLE_NOISE_LINE.match(cleaned):
            continue
        if cleaned.startswith("888"):
            continue
        # Drop pure page chrome
        if re.fullmatch(r"[\d\W]+", cleaned):
            continue
        lines.append(cleaned)
    if not lines:
        return None

    # Prefer the trailing content block (closest to Course Number) when many lines match
    if len(lines) > 3:
        lines = lines[-3:]

    title = " ".join(lines)
    title = re.sub(r"\s+", " ", title).strip(" \t-|•·")
    # Soft-join hyphenated line wraps: "Non-Project - Managers" / "Finance — Self"
    title = re.sub(r"\s*[—–-]\s+", " — ", title)
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) < 4:
        return None
    return title


def is_weak_course_title(title: str | None) -> bool:
    """True when a title looks truncated or is a generic single fragment."""
    if not title:
        return True
    cleaned = re.sub(r"\s+", " ", str(title)).strip()
    if len(cleaned) < 8:
        return True
    lower = cleaned.lower().rstrip(".:")
    if lower in _WEAK_TITLE_WORDS:
        return True
    words = lower.split()
    # Single short token is almost always a wrapped-line fragment ("Managers")
    if len(words) == 1 and len(cleaned) < 18:
        return True
    if cleaned.endswith(("—", "-", "–")):
        return True
    return False


def prefer_course_title(*candidates: str | None) -> str | None:
    """Pick the strongest non-empty title among candidates."""
    best: str | None = None
    best_score = float("-inf")
    for raw in candidates:
        if not raw:
            continue
        title = re.sub(r"\s+", " ", str(raw)).strip()
        # Strip accidental markdown heading markers
        title = re.sub(r"^#{1,6}\s*", "", title).strip()
        if not title:
            continue
        score = float(len(title))
        if is_weak_course_title(title):
            score -= 40.0
        if score > best_score:
            best = title
            best_score = score
    return best


def extract_course_title(text: str, base_metadata: dict[str, Any] | None = None) -> str | None:
    metadata = base_metadata or {}
    meta_title = None
    for key in ("course_title", "title"):
        value = metadata.get(key)
        if value:
            meta_title = str(value).strip()
            break

    from_text: str | None = None
    before_number = COURSE_TITLE_BEFORE_NUMBER_PATTERN.search(text or "")
    if before_number:
        from_text = _normalize_title_candidate(before_number.group(1))

    if not from_text:
        header_match = COURSE_HEADER_TITLE_PATTERN.search(text or "")
        if header_match:
            from_text = _normalize_title_candidate(header_match.group(1))

    # Prefer longer / non-weak recovered title over short stored metadata
    return prefer_course_title(from_text, meta_title)


def extract_duration(text: str, base_metadata: dict[str, Any] | None = None) -> str | None:
    metadata = base_metadata or {}
    for key in ("duration", "length"):
        value = metadata.get(key)
        if value:
            return str(value).strip()

    match = LENGTH_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


def extract_price(text: str, base_metadata: dict[str, Any] | None = None) -> str | None:
    metadata = base_metadata or {}
    for key in ("price", "cost", "tuition"):
        value = metadata.get(key)
        if value:
            return str(value).strip()

    match = PRICE_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


def extract_delivery_method(text: str, base_metadata: dict[str, Any] | None = None) -> str | None:
    metadata = base_metadata or {}
    value = metadata.get("delivery_method")
    if value:
        return str(value).strip()

    match = DELIVERY_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


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


def build_course_metadata(
    *,
    text: str,
    source_path: str,
    base_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract structured course fields used for retrieval and display."""
    base = dict(base_metadata or {})
    course_meta: dict[str, Any] = {}

    course_id = extract_primary_course_id(text, source_path=source_path)
    if course_id:
        course_meta["course_id"] = course_id

    course_ids = extract_course_ids(text, source_path=source_path)
    if course_ids:
        course_meta["course_ids"] = course_ids

    course_title = extract_course_title(text, base)
    if course_title:
        course_meta["course_title"] = course_title

    duration = extract_duration(text, base)
    if duration:
        course_meta["duration"] = duration

    price = extract_price(text, base)
    if price:
        course_meta["price"] = price

    delivery_method = extract_delivery_method(text, base)
    if delivery_method:
        course_meta["delivery_method"] = delivery_method

    if base.get("department"):
        course_meta["department"] = str(base["department"]).strip()

    return course_meta


def merge_course_metadata(*metadata_dicts: dict[str, Any] | None) -> dict[str, Any]:
    """Merge course metadata, preferring the first non-empty value for each key."""
    merged: dict[str, Any] = {}
    for metadata in metadata_dicts:
        if not metadata:
            continue
        for key in COURSE_METADATA_KEYS:
            value = metadata.get(key)
            if value and key not in merged:
                merged[key] = value
        extra_ids = metadata.get("course_ids")
        if extra_ids and "course_ids" not in merged:
            merged["course_ids"] = extra_ids
    return merged


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

    metadata.update(build_course_metadata(text=text, source_path=source_path, base_metadata=metadata))

    headings = extract_headings(text)
    if headings and "section_title" not in metadata:
        metadata["section_title"] = headings[0]["title"]
    if headings:
        metadata["headings"] = headings

    metadata.setdefault("file_name", Path(source_path).name)

    return metadata