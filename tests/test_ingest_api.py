"""API tests for the single POST /ingest endpoint."""

from io import BytesIO
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def _fake_result(**overrides):
    result = MagicMock()
    result.action = overrides.get("action", "indexed")
    result.message = overrides.get("message", "ok")
    result.source_path = overrides.get("source_path", "data/x.pdf")
    result.chunk_count = overrides.get("chunk_count", 3)
    result.skipped_duplicate_chunks = overrides.get("skipped_duplicate_chunks", 0)
    return result


def test_ingest_requires_source():
    response = client.post("/ingest", json={})
    assert response.status_code == 400
    assert "file" in response.json()["detail"].lower() or "url" in response.json()["detail"].lower()


def test_ingest_url_json():
    with patch("src.chatbot.chatbot.get_index", return_value=object()), \
         patch("src.ingestion.pipeline.IngestionPipeline") as pipeline_cls:
        pipeline_cls.return_value.ingest_url.return_value = _fake_result(
            source_path="https://example.com/c",
            message="indexed url",
        )
        response = client.post(
            "/ingest",
            json={"url": "https://example.com/c", "force": True},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["chunks_processed"] == 3
    pipeline_cls.return_value.ingest_url.assert_called_once_with(
        "https://example.com/c", force=True
    )


def test_ingest_file_multipart():
    with patch("src.chatbot.chatbot.get_index", return_value=object()), \
         patch("src.ingestion.pipeline.IngestionPipeline") as pipeline_cls, \
         patch("src.api.router.ingest.save_uploaded_file", return_value="data/note.txt"):
        pipeline_cls.return_value.ingest_file.return_value = _fake_result(
            source_path="data/note.txt",
            message="indexed file",
        )
        response = client.post(
            "/ingest",
            files={"file": ("note.txt", BytesIO(b"hello"), "text/plain")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    pipeline_cls.return_value.ingest_file.assert_called_once_with("data/note.txt", force=True)


def test_ingest_rejects_invalid_url_scheme():
    response = client.post("/ingest", json={"url": "ftp://example.com/x"})
    assert response.status_code == 400
