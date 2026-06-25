from pathlib import Path

from src.ingestion.pricing import (
    apply_catalog_prices,
    is_gsa_price_list,
    parse_course_prices_from_gsa_text,
    save_price_catalog,
    clear_price_catalog_cache,
    lookup_course_price,
)


def test_is_gsa_price_list_detects_filename():
    assert is_gsa_price_list("GSA-Price-List_03162026.pdf") is True
    assert is_gsa_price_list("4606.pdf") is False


def test_parse_cots_tier_price_line():
    text = "5117 Federal Financial Management Systems Requirements 2 $8,596.00"
    prices = parse_course_prices_from_gsa_text(text)
    assert prices["5117"] == "$8,596.00"


def test_parse_oe_and_virtual_price_lines_for_course_4606():
    text = """
    Data Visualization 4606 $908.69 $4,543.00 $859.86 $8,598.00 $810.91 $40,545.00 $762.06 $76,206.00
    Data Visualization 4606 $654.71 $13,094.00 $566.71 $14,167.00 $498.30 $14,949.00
    """
    prices = parse_course_prices_from_gsa_text(text)
    assert prices["4606"] == "$14,949.00"


def test_apply_catalog_prices_fills_missing_price(tmp_path, monkeypatch):
    monkeypatch.setenv("COURSE_PRICE_CATALOG_PATH", str(tmp_path / "course_prices.json"))
    clear_price_catalog_cache()
    save_price_catalog({"4606": "$14,949.00"})

    metadata = apply_catalog_prices({"course_id": "4606", "course_title": "Data Visualization"})
    assert metadata["price"] == "$14,949.00"
    assert lookup_course_price("4606") == "$14,949.00"


def test_parse_real_gsa_price_list_sample():
    gsa_path = Path(r"C:\Users\user\Desktop\Pdf\managementconcepts_pdfs\GSA-Price-List_03162026.pdf")
    if not gsa_path.exists():
        return

    from src.ingestion.loaders import load_pdf

    documents = load_pdf(gsa_path)
    full_text = "\n".join(doc.text for doc in documents)
    prices = parse_course_prices_from_gsa_text(full_text)
    assert "4606" in prices
    assert prices["4606"].startswith("$")