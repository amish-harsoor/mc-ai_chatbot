"""Session lifecycle: start, history, and message persistence."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException

from src.api.router.deps import require_session_uuid, resolve_request_owner
from src.api.schemas import SaveMessageRequest, StartSessionRequest, StartSessionResponse

logger = logging.getLogger("mc_ai_chatbot")

router = APIRouter(tags=["sessions"])


@router.post("/session/start", response_model=StartSessionResponse)
async def start_session(request: StartSessionRequest = StartSessionRequest()):
    """
    Create a new chat session for a guest or registered owner.

    Pass user_id when logged in, or guest_id for anonymous (stable browser id).
    If neither is sent, a guest_id is derived from the new session_id.
    Response may include a durable profile snapshot for the owner (no separate call).

    Set reset_profile=true (New chat) to clear durable preferences and start
    onboarding without restoring prior experience / department / goal.
    """
    from src.db.profiles import (
        clear_learner_profile,
        create_session,
        get_learner_profile,
        resolve_owner,
    )

    session_id = str(uuid.uuid4())
    try:
        owner_id, owner_type = resolve_owner(
            user_id=request.user_id,
            guest_id=request.guest_id or f"guest_{session_id}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if request.reset_profile:
        clear_learner_profile(owner_id)

    session = create_session(
        session_id,
        owner_id=owner_id,
        owner_type=owner_type,
        seed_from_profile=not request.reset_profile,
    )
    profile = None if request.reset_profile else get_learner_profile(owner_id)
    return StartSessionResponse(
        session_id=session["session_id"],
        owner_id=owner_id,
        owner_type=owner_type,
        profile=profile,
    )


@router.get("/session/{session_id}/history")
async def get_history(session_id: str):
    """Return full message history for one session (plus optional condensed prefs snapshot)."""
    from src.db.profiles import get_session
    from src.db.session_manager import get_session_history_raw

    require_session_uuid(session_id)

    messages = get_session_history_raw(session_id)
    session = None
    try:
        session = get_session(session_id)
    except Exception as e:
        # Condensed snapshot is optional for history UI; never block full chat restore
        logger.warning("Failed to load condensed session snapshot for %s: %s", session_id, e)
    return {
        "session_id": session_id,
        "messages": messages,
        "session": session,
    }


@router.post("/session/{session_id}/message")
async def save_session_message(session_id: str, request: SaveMessageRequest):
    """
    Persist one user or assistant message without generating a reply.

    Use for onboarding UI, welcome copy, and preference chips. For a bot answer,
    call POST /chat/stream instead.
    """
    from src.db.session_manager import save_message

    require_session_uuid(session_id)

    if request.role not in ("user", "assistant"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'assistant'.")

    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty.")

    user_id, guest_id = resolve_request_owner(
        user_id=request.user_id,
        guest_id=request.guest_id,
        session_id=session_id,
    )
    save_message(
        session_id,
        request.role,
        request.content,
        display_content=request.display_content or request.content,
        metadata=request.metadata,
        user_id=user_id,
        guest_id=guest_id,
    )
    return {"status": "ok", "session_id": session_id}
