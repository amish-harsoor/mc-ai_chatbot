import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

DOLLAR_AMOUNT = r"\$[\d,]+(?:\.\d{2})?"
COTS_PRICE_LINE = re.compile(
    rf"^\s*(\d{{4,6}})\s+(.+?)\s+(\d+(?:\.\d+)?)\s+({DOLLAR_AMOUNT})\s*$",
    re.MULTILINE,
)
TITLE_ID_PRICE_LINE = re.compile(
    rf"^\s*(.+?)\s+(\d{{4,6}})\s+((?:{DOLLAR_AMOUNT}\s*)+)$",
    re.MULTILINE,
)
ID_ONLY_PRICE_LINE = re.compile(
    rf"^\s*(\d{{4,6}})\s+((?:{DOLLAR_AMOUNT}\s*)+)$",
    re.MULTILINE,
)

_SOURCE_PRIORITY = {"cots": 3, "virtual": 2, "oe": 1, "id_only": 0}
_catalog_cache: dict[str, str] | None = None


def _catalog_path() -> Path:
    return Path(os.getenv("COURSE_PRICE_CATALOG_PATH", "data/course_prices.json"))


def is_gsa_price_list(source_path: str | Path, text: str = "") -> bool:
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


def _parse_dollar_amounts(raw: str) -> list[str]:
    return re.findall(DOLLAR_AMOUNT, raw)


def _select_display_price(amounts: list[str], *, layout: str) -> str | None:
    if not amounts:
        return None
    if layout == "cots":
        return amounts[0]
    if layout == "virtual" and len(amounts) >= 6:
        return amounts[5]
    if layout == "oe" and len(amounts) >= 4:
        return amounts[3]
    if len(amounts) >= 2:
        return amounts[-2]
    return amounts[-1]


def _upsert_price(
    catalog: dict[str, dict[str, str]],
    course_id: str,
    price: str,
    *,
    source: str,
) -> None:
    current = catalog.get(course_id)
    if current and _SOURCE_PRIORITY[current["source"]] >= _SOURCE_PRIORITY[source]:
        return
    catalog[course_id] = {"price": price, "source": source}


def parse_course_prices_from_gsa_text(text: str) -> dict[str, str]:
    """Extract course_id -> display price mappings from a GSA price list document."""
    catalog: dict[str, dict[str, str]] = {}

    for match in COTS_PRICE_LINE.finditer(text):
        _upsert_price(catalog, match.group(1), match.group(4), source="cots")

    for match in TITLE_ID_PRICE_LINE.finditer(text):
        amounts = _parse_dollar_amounts(match.group(3))
        layout = "virtual" if len(amounts) == 6 else "oe"
        price = _select_display_price(amounts, layout=layout)
        if price:
            _upsert_price(catalog, match.group(2), price, source=layout)

    for match in ID_ONLY_PRICE_LINE.finditer(text):
        amounts = _parse_dollar_amounts(match.group(2))
        price = _select_display_price(amounts, layout="oe")
        if price:
            _upsert_price(catalog, match.group(1), price, source="id_only")

    return {course_id: entry["price"] for course_id, entry in catalog.items()}


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


def update_price_catalog_from_text(text: str) -> dict[str, str]:
    parsed = parse_course_prices_from_gsa_text(text)
    if not parsed:
        return load_price_catalog()

    catalog = load_price_catalog()
    catalog.update(parsed)
    save_price_catalog(catalog)
    return catalog


def lookup_course_price(course_id: str | int | None) -> str | None:
    if course_id is None:
        return None
    return load_price_catalog().get(str(course_id))


def apply_catalog_prices(metadata: dict) -> dict:
    """Fill missing price on course metadata from the GSA catalog."""
    course_id = metadata.get("course_id")
    if course_id and not metadata.get("price"):
        price = lookup_course_price(course_id)
        if price:
            metadata = {**metadata, "price": price}
    return metadata


def clear_price_catalog_cache() -> None:
    global _catalog_cache
    _catalog_cache = None


def ensure_price_catalog_from_directory(data_dir: str | Path) -> dict[str, str]:
    """Build the catalog from any GSA price list PDFs found under data_dir."""
    from src.ingestion.loaders import load_pdf

    root = Path(data_dir)
    if not root.exists():
        return load_price_catalog()

    catalog = load_price_catalog()
    for path in sorted(root.rglob("*.pdf")):
        if not is_gsa_price_list(path):
            continue
        try:
            documents = load_pdf(path)
            full_text = "\n".join(doc.text for doc in documents)
            parsed = parse_course_prices_from_gsa_text(full_text)
            if parsed:
                catalog.update(parsed)
                logger.info(
                    "Parsed %s course prices from %s",
                    len(parsed),
                    path.name,
                )
        except Exception as exc:
            logger.warning("Failed to parse GSA price list %s: %s", path, exc)

    if catalog:
        save_price_catalog(catalog)
    return catalog