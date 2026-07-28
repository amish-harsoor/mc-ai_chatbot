"""Shared helpers used across API route modules."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile

logger = logging.getLogger("mc_ai_chatbot")

SUPPORTED_UPLOAD_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}


def resolve_request_owner(
    *,
    user_id: str | None,
    guest_id: str | None,
    session_id: str | None = None,
) -> tuple[str | None, str | None]:
    """Return (user_id, guest_id), minting a guest from session_id if neither given."""
    if user_id and str(user_id).strip():
        return str(user_id).strip(), None
    if guest_id and str(guest_id).strip():
        return None, str(guest_id).strip()
    if session_id:
        return None, f"guest_{session_id}"
    return None, None


def save_uploaded_file(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. Allowed: "
                f"{', '.join(sorted(SUPPORTED_UPLOAD_EXTENSIONS))}"
            ),
        )

    os.makedirs("data", exist_ok=True)
    file_path = os.path.join("data", file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path


def require_session_uuid(session_id: str) -> None:
    import uuid

    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format.")
