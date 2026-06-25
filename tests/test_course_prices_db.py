from unittest.mock import MagicMock, patch

from src.db import course_prices


def _mock_db_connection():
    mock_cursor = MagicMock()
    mock_cursor.__enter__.return_value = mock_cursor
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


def test_init_course_prices_table_creates_schema():
    mock_conn, mock_cursor = _mock_db_connection()

    with patch("src.db.course_prices.get_connection", return_value=mock_conn):
        course_prices.init_course_prices_table()

    assert mock_cursor.execute.call_count == 2
    mock_conn.commit.assert_called_once()


def test_upsert_price_catalog_to_db_writes_rows():
    mock_conn, mock_cursor = _mock_db_connection()

    with patch("src.db.course_prices.get_connection", return_value=mock_conn), patch(
        "src.db.course_prices.init_course_prices_table"
    ), patch("src.db.course_prices.execute_values") as execute_values_mock:
        count = course_prices.upsert_price_catalog_to_db(
            {"4606": "$14,949.00", "5117": "$8,596.00"}
        )

    assert count == 2
    execute_values_mock.assert_called_once()
    mock_conn.commit.assert_called_once()


def test_load_price_catalog_prefers_database(tmp_path, monkeypatch):
    from src.ingestion.pricing import clear_price_catalog_cache, load_price_catalog

    monkeypatch.setenv("COURSE_PRICE_CATALOG_PATH", str(tmp_path / "course_prices.json"))
    clear_price_catalog_cache()

    with patch(
        "src.db.course_prices.load_price_catalog_from_db",
        return_value={"4606": "$14,949.00"},
    ):
        catalog = load_price_catalog()

    assert catalog == {"4606": "$14,949.00"}