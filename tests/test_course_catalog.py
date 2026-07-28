"""Official course catalog (management_concepts_courses.json)."""

from pathlib import Path

import pytest

from src.ingestion.course_catalog import (
    apply_official_catalog,
    format_catalog_price,
    get_course,
    load_course_catalog,
    price_map,
    title_map,
)


@pytest.fixture(autouse=True)
def _reload_catalog(monkeypatch):
    from src.ingestion import course_catalog as cc

    path = Path(__file__).resolve().parents[1] / "data" / "management_concepts_courses.json"
    if not path.is_file():
        pytest.skip("Official course catalog JSON not present")
    monkeypatch.setenv("COURSE_CATALOG_PATH", str(path))
    cc.clear_course_catalog_cache()
    yield
    cc.clear_course_catalog_cache()


def test_load_catalog_has_hundreds_of_courses():
    catalog = load_course_catalog(force=True)
    assert len(catalog) >= 300
    assert "6131" in catalog
    assert catalog["6131"]["title"] == "Project Management Essentials for Non-Project Managers"


def test_known_titles_and_prices():
    c = get_course("6100")
    assert c is not None
    assert "Project Management Principles" in c["title"]
    assert c.get("duration")

    # Course with a known price in the export
    priced = next(iter(price_map().items()))
    cid, price = priced
    assert cid.isdigit()
    assert price.startswith("$")


def test_format_catalog_price():
    assert format_catalog_price(1429.0, "$1429.00") == "$1429.00"
    assert format_catalog_price(1429.0) == "$1,429"
    assert format_catalog_price(None) is None


def test_apply_official_catalog_overlays_metadata():
    meta = apply_official_catalog({"course_id": "4000", "course_title": "Managers"})
    assert meta["course_title"] == "Leadership and Management Skills for Non-Managers"
    assert meta.get("duration")
    # price may or may not exist for 4000; title must win over truncated value
    assert meta["course_title"] != "Managers"


def test_title_map_covers_catalog():
    titles = title_map()
    assert len(titles) >= 300
    assert titles["5051"] == "Federal Financial Management Overview"
