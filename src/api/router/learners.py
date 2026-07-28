"""Learner profile and session listing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["learners"])


@router.get("/learner/{owner_id}/profile")
async def get_owner_profile(owner_id: str):
    """Durable condensed profile for a guest or registered owner."""
    from src.db.profiles import get_learner_profile

    profile = get_learner_profile(owner_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return profile


@router.get("/learner/{owner_id}/sessions")
async def list_owner_sessions(owner_id: str, limit: int = 50):
    """List condensed session snapshots for an owner (full chats via /history per session)."""
    from src.db.profiles import list_sessions_for_owner

    sessions = list_sessions_for_owner(owner_id, limit=limit)
    return {"owner_id": owner_id, "sessions": sessions}
