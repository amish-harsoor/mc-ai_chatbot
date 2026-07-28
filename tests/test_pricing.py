from src.ingestion.pricing import (
    apply_catalog_prices,
    clear_price_catalog_cache,
    is_gsa_price_list,
    lookup_course_price,
    save_price_catalog,
)


def test_is_gsa_price_list_detects_filename():
    assert is_gsa_price_list("GSA-Price-List_03162026.pdf") is True
    assert is_gsa_price_list("4606.pdf") is False


def test_apply_catalog_prices_prefers_official_catalog_for_4606(tmp_path, monkeypatch):
    """Official MC JSON ($1409.00) wins over any secondary price-catalog value."""
    monkeypatch.setenv("COURSE_PRICE_CATALOG_PATH", str(tmp_path / "course_prices.json"))
    clear_price_catalog_cache()
    save_price_catalog({"4606": "$14,949.00"})

    metadata = apply_catalog_prices(
        {"course_id": "4606", "course_title": "Data Visualization"}
    )
    assert metadata["price"] == "$1409.00"
    assert lookup_course_price("4606") == "$14,949.00"


def test_apply_catalog_prices_fills_from_secondary_when_not_in_official(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("COURSE_PRICE_CATALOG_PATH", str(tmp_path / "course_prices.json"))
    clear_price_catalog_cache()
    save_price_catalog({"999001": "$1,234.00"})

    metadata = apply_catalog_prices(
        {"course_id": "999001", "course_title": "Fake Course"}
    )
    assert metadata["price"] == "$1,234.00"
    assert lookup_course_price("999001") == "$1,234.00"
