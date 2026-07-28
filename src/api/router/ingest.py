"""Knowledge-base ingestion — single entry point for files or URLs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import UploadFile

from src.api.router.deps import save_uploaded_file
from src.api.schemas import IngestRequest

logger = logging.getLogger("mc_ai_chatbot")

router = APIRouter(tags=["ingest"])


def _result_payload(result, *, default_message: str = "") -> dict:
    return {
        "status": "success" if result.action == "indexed" else result.action,
        "message": result.message or default_message,
        "source_path": result.source_path,
        "chunks_processed": result.chunk_count,
        "skipped_duplicate_chunks": result.skipped_duplicate_chunks,
    }


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


async def _parse_ingest_source(request: Request) -> tuple[UploadFile | None, str | None, bool]:
    """
    Resolve exactly one source from the request.

    - application/json → {"url": "...", "force": false}
    - multipart/form-data → file and/or url + force form fields
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            data = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
        try:
            body = IngestRequest.model_validate(data)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid ingest body.") from exc
        url = (body.url or "").strip() or None
        return None, url, body.force

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        raw_file = form.get("file")
        file: UploadFile | None = raw_file if isinstance(raw_file, UploadFile) else None
        if file is not None and not (file.filename or "").strip():
            file = None
        url = str(form.get("url") or "").strip() or None
        force = _as_bool(form.get("force"), default=False)
        return file, url, force

    raise HTTPException(
        status_code=415,
        detail="Use application/json (url) or multipart/form-data (file or url).",
    )


@router.post("/ingest")
async def ingest(request: Request):
    """
    Ingest one source into the vector store.

    Exactly one of **file** or **url**:

    - **File** — ``multipart/form-data`` with field ``file`` (PDF / MD / TXT).
      Re-uploads always force re-index.
    - **URL** — JSON ``{"url": "https://...", "force": false}`` or form field ``url``.
    """
    from src.chatbot.chatbot import get_index
    from src.ingestion.pipeline import IngestionPipeline

    file, source_url, source_force = await _parse_ingest_source(request)

    if file is not None and source_url:
        raise HTTPException(
            status_code=400,
            detail="Provide either a file or a url, not both.",
        )
    if file is None and not source_url:
        raise HTTPException(
            status_code=400,
            detail="Provide a file (multipart) or a url (JSON/form).",
        )

    try:
        pipeline = IngestionPipeline(index=get_index())
        if file is not None:
            file_path = save_uploaded_file(file)
            result = pipeline.ingest_file(file_path, force=True)
            return _result_payload(result, default_message=f"Processed {file.filename}")

        assert source_url is not None
        if not source_url.lower().startswith(("http://", "https://")):
            raise HTTPException(
                status_code=400,
                detail="URL must start with http:// or https://",
            )
        result = pipeline.ingest_url(source_url, force=source_force)
        return _result_payload(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ingest failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to ingest: {e}") from e
