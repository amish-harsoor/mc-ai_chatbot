"""Canonical Management Concepts course catalog from official JSON export.

Source of truth for display fields used in chat headers:
  course_id, title, duration, level, credits, url, price

Default file: data/management_concepts_courses.json
Override with COURSE_CATALOG_PATH.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_catalog_by_id: dict[str, dict[str, Any]] | None = None


def _default_catalog_path() -> Path:
    env = os.getenv("COURSE_CATALOG_PATH", "").strip()
    if env:
        return Path(env)
    # project_root/data/...  (src/ingestion -> parents[2])
    root = Path(__file__).resolve().parents[2]
    return root / "data" / "management_concepts_courses.json"


def format_catalog_price(value: Any, price_raw: Any = None) -> str | None:
    """Normalize catalog price for display (e.g. $1,429.00)."""
    if price_raw is not None and str(price_raw).strip():
        raw = str(price_raw).strip()
        if raw.startswith("$") or re.search(r"\d", raw):
            return raw

    if value is None or value == "":
        return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.startswith("$"):
            return s
        try:
            value = float(s.replace(",", ""))
        except ValueError:
            return s

    try:
        amount = float(value)
    except (TypeError, ValueError):
        return str(value)

    if amount < 0:
        return None
    # Whole dollars without cents noise when clean
    if abs(amount - round(amount)) < 1e-9:
        return f"${int(round(amount)):,}"
    return f"${amount:,.2f}"


def _normalize_entry(raw: dict[str, Any]) -> dict[str, Any] | None:
    course_id = raw.get("course_id")
    if course_id is None or str(course_id).strip() == "":
        return None
    cid = str(course_id).strip()
    title = (raw.get("title") or "").strip() or None
    duration = (raw.get("duration") or "").strip() or None
    level = (raw.get("level") or "").strip() or None
    credits = (raw.get("credits") or "").strip() or None
    url = (raw.get("url") or "").strip() or None
    if not url:
        url = f"https://www.managementconcepts.com/product/{cid}"

    price = format_catalog_price(raw.get("price"), raw.get("price_raw"))

    entry: dict[str, Any] = {
        "course_id": cid,
        "title": title,
        "course_title": title,
        "duration": duration,
        "level": level,
        "credits": credits,
        "url": url,
    }
    if price:
        entry["price"] = price
    return entry


def load_course_catalog(force: bool = False) -> dict[str, dict[str, Any]]:
    """Return course_id -> normalized catalog entry."""
    global _catalog_by_id
    if _catalog_by_id is not None and not force:
        return _catalog_by_id

    path = _default_catalog_path()
    catalog: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        logger.warning("Course catalog file not found: %s", path)
        _catalog_by_id = catalog
        return catalog

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to read course catalog %s: %s", path, exc)
        _catalog_by_id = catalog
        return catalog

    if not isinstance(data, list):
        logger.error("Course catalog must be a JSON list, got %s", type(data).__name__)
        _catalog_by_id = catalog
        return catalog

    for raw in data:
        if not isinstance(raw, dict):
            continue
        entry = _normalize_entry(raw)
        if entry:
            catalog[entry["course_id"]] = entry

    _catalog_by_id = catalog
    with_price = sum(1 for e in catalog.values() if e.get("price"))
    logger.info(
        "Official course catalog ready (%s courses, %s with price) from %s",
        len(catalog),
        with_price,
        path,
    )
    return catalog


def clear_course_catalog_cache() -> None:
    global _catalog_by_id
    _catalog_by_id = None


def get_course(course_id: str | int | None) -> dict[str, Any] | None:
    if course_id is None:
        return None
    return load_course_catalog().get(str(course_id).strip())


def get_course_price(course_id: str | int | None) -> str | None:
    entry = get_course(course_id)
    return entry.get("price") if entry else None


def title_map() -> dict[str, str]:
    return {
        cid: entry["title"]
        for cid, entry in load_course_catalog().items()
        if entry.get("title")
    }


def price_map() -> dict[str, str]:
    return {
        cid: entry["price"]
        for cid, entry in load_course_catalog().items()
        if entry.get("price")
    }


def apply_official_catalog(metadata: dict[str, Any]) -> dict[str, Any]:
    """Overlay official catalog fields onto chunk metadata (canonical wins).

    Always includes price when present in the official catalog.
    """
    course_id = metadata.get("course_id")
    if not course_id:
        return metadata

    entry = get_course(course_id)
    if not entry:
        return metadata

    out = dict(metadata)
    if entry.get("title"):
        out["course_title"] = entry["title"]
        out["title"] = entry["title"]
    if entry.get("duration"):
        out["duration"] = entry["duration"]
    if entry.get("level"):
        out["level"] = entry["level"]
    if entry.get("credits"):
        out["credits"] = entry["credits"]
    if entry.get("url"):
        out["url"] = entry["url"]
    if entry.get("price"):
        out["price"] = entry["price"]
    return out


def sync_prices_to_price_catalog() -> dict[str, str]:
    """Replace shared price catalog (DB + JSON) with official MC JSON prices only."""
    prices = price_map()
    if not prices:
        return {}
    try:
        from src.ingestion.pricing import replace_price_catalog

        replace_price_catalog(prices)
        logger.info(
            "Replaced price catalog with %s official MC prices (DB + JSON)",
            len(prices),
        )
        return prices
    except Exception as exc:
        logger.warning("Failed to sync official prices: %s", exc)
        return prices
