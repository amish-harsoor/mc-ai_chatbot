from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    """Identity for the chat owner. Prefer user_id when logged in; else guest_id."""

    user_id: Optional[str] = Field(default=None, max_length=255)
    guest_id: Optional[str] = Field(default=None, max_length=255)
    # When true (New chat), wipe durable learner prefs so onboarding starts clean.
    reset_profile: bool = False


class StartSessionResponse(BaseModel):
    session_id: str
    owner_id: str
    owner_type: Literal["guest", "registered"]
    profile: Optional[dict[str, Any]] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str
    display_message: Optional[str] = None
    silent_response: bool = False
    metadata: Optional[dict] = None
    user_id: Optional[str] = Field(default=None, max_length=255)
    guest_id: Optional[str] = Field(default=None, max_length=255)


class SaveMessageRequest(BaseModel):
    role: str
    content: str
    display_content: Optional[str] = None
    metadata: Optional[dict] = None
    user_id: Optional[str] = Field(default=None, max_length=255)
    guest_id: Optional[str] = Field(default=None, max_length=255)


class IngestRequest(BaseModel):
    """JSON body for URL ingestion. For files, send multipart form field ``file`` instead."""

    url: Optional[str] = None
    force: bool = False
