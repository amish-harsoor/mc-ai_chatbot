from unittest.mock import MagicMock, patch

from src.db import reset, status


def test_get_ingestion_status_reads_counts():
    mock_rows = {
        "vector": {"count": 42},
        "registry": {"count": 3},
        "chat": {"count": 10},
        "sources": [
            {
                "source_path": "/tmp/a.pdf",
                "source_type": "pdf",
                "chunk_count": 7,
                "updated_at": None,
            }
        ],
    }
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [
        mock_rows["vector"],
        mock_rows["registry"],
        mock_rows["chat"],
    ]
    mock_cursor.fetchall.return_value = mock_rows["sources"]
    mock_cursor.__enter__.return_value = mock_cursor

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn

    with patch("src.db.status.get_connection", return_value=mock_conn), patch(
        "src.db.status._table_exists", return_value=True
    ), patch("src.db.status.get_vector_table_name", return_value="data_vectors"), patch(
        "src.db.status.db_label", return_value="Supabase"
    ):
        result = status.get_ingestion_status()

    assert result["vector_count"] == 42
    assert result["registry_count"] == 3
    assert result["chat_message_count"] == 10
    assert len(result["sources"]) == 1


def test_wipe_ingestion_data_truncates_tables():
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [1]
    mock_cursor.__enter__.return_value = mock_cursor

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("src.db.reset.get_connection", return_value=mock_conn), patch(
        "src.db.reset._table_exists", return_value=True
    ), patch("src.db.reset.get_vector_table_name", return_value="data_vectors"), patch(
        "src.db.reset.db_label", return_value="Supabase"
    ), patch("src.chatbot.retrieval.clear_bm25_cache"):
        result = reset.wipe_ingestion_data()

    assert result["backend"] == "Supabase"
    assert mock_cursor.execute.called
    mock_conn.commit.assert_called_once()