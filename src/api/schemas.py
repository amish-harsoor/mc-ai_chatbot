from typing import Optional

from pydantic import BaseModel


class StartSessionResponse(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    display_message: Optional[str] = None
    silent_response: bool = False
    metadata: Optional[dict] = None


class SaveMessageRequest(BaseModel):
    role: str
    content: str
    display_content: Optional[str] = None
    metadata: Optional[dict] = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str


class IngestUrlRequest(BaseModel):
    url: str
    force: bool = False