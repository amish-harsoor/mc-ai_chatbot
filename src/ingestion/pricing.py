"""Course price catalog: DB + optional JSON mirror.

Source of truth for learner-facing prices is the official Management Concepts
course JSON (see course_catalog.py). This module stores/loads the shared
course_id -> display price map used as a fallback when metadata has no price.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_catalog_cache: dict[str, str] | None = None


def _catalog_path() -> Path:
    return Path(os.getenv("COURSE_PRICE_CATALOG_PATH", "data/course_prices.json"))


def is_gsa_price_list(source_path: str | Path, text: str = "") -> bool:
    """Detect GSA bulk price-list PDFs so ingest can skip treating them as courses."""
    name = Path(source_path).name.lower()
    if "price-list" in name or "price list" in name:
        return True
    if "gsa" in name and "price" in name:
        return True

    sample = (text or "")[:8000].lower()
    return (
        "gsa mas price list" in sample
        or "fss price list" in sample
        or "government awarded prices" in sample
    )


def _load_json_catalog() -> dict[str, str]:
    path = _catalog_path()
    if not path.is_file():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception as exc:
        logger.warning("Failed to load course price catalog from %s: %s", path, exc)
    return {}


def _save_json_catalog(catalog: dict[str, str]) -> None:
    if os.getenv("COURSE_PRICE_CATALOG_JSON", "true").lower() != "true":
        return

    path = _catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2, sort_keys=True), encoding="utf-8")
    logger.info("Saved %s course prices to %s", len(catalog), path)


def _load_db_catalog() -> dict[str, str]:
    try:
        from src.db.course_prices import load_price_catalog_from_db

        return load_price_catalog_from_db()
    except Exception as exc:
        logger.warning("Failed to load course price catalog from database: %s", exc)
        return {}


def _save_db_catalog(catalog: dict[str, str]) -> None:
    try:
        from src.db.course_prices import upsert_price_catalog_to_db

        upsert_price_catalog_to_db(catalog)
    except Exception as exc:
        logger.warning("Failed to save course price catalog to database: %s", exc)


def load_price_catalog() -> dict[str, str]:
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache

    catalog = _load_db_catalog()
    if not catalog:
        catalog = _load_json_catalog()
        if catalog:
            _save_db_catalog(catalog)

    _catalog_cache = catalog
    return _catalog_cache


def save_price_catalog(catalog: dict[str, str]) -> None:
    global _catalog_cache
    _save_db_catalog(catalog)
    _save_json_catalog(catalog)
    _catalog_cache = dict(catalog)


def replace_price_catalog(catalog: dict[str, str]) -> dict[str, str]:
    """Replace DB + JSON catalogs entirely (drops rows not in catalog)."""
    global _catalog_cache
    try:
        from src.db.course_prices import replace_price_catalog_in_db

        replace_price_catalog_in_db(catalog)
    except Exception as exc:
        logger.warning("Failed to replace course price catalog in database: %s", exc)
    _save_json_catalog(catalog)
    _catalog_cache = dict(catalog)
    return _catalog_cache


def lookup_course_price(course_id: str | int | None) -> str | None:
    if course_id is None:
        return None
    return load_price_catalog().get(str(course_id))


def apply_catalog_prices(metadata: dict) -> dict:
    """Fill missing price on course metadata from official catalog, then DB/JSON."""
    course_id = metadata.get("course_id")
    if not course_id:
        return metadata

    if not metadata.get("price"):
        try:
            from src.ingestion.course_catalog import get_course_price

            official = get_course_price(course_id)
            if official:
                return {**metadata, "price": official}
        except Exception:
            pass

    if not metadata.get("price"):
        price = lookup_course_price(course_id)
        if price:
            return {**metadata, "price": price}
    return metadata


def clear_price_catalog_cache() -> None:
    global _catalog_cache
    _catalog_cache = None
