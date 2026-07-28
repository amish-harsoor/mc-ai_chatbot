"""
Thin HTTP client for calling the chatbot microservice from any Python app
(FastAPI, Django, scripts, etc.).

Usage:
    from src.client import ChatbotClient

    client = ChatbotClient("http://localhost:8000", api_key="secret")
    session = client.start_session(guest_id="guest_abc")
    for chunk in client.chat_stream(session["session_id"], "Recommend PM courses", guest_id="guest_abc"):
        print(chunk, end="")
"""

from __future__ import annotations

from typing import Any, Iterator

import httpx


class ChatbotClient:
    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        prefix: str = "",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.prefix = prefix.rstrip("/")
        if self.prefix and not self.prefix.startswith("/"):
            self.prefix = f"/{self.prefix}"
        self.timeout = timeout
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["X-API-Key"] = api_key

    def _url(self, path: str) -> str:
        return f"{self.base_url}{self.prefix}{path}"

    def health(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
            response = client.get(self._url("/health"))
            response.raise_for_status()
            return response.json()

    def start_session(
        self,
        *,
        user_id: str | None = None,
        guest_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if user_id is not None:
            payload["user_id"] = user_id
        if guest_id is not None:
            payload["guest_id"] = guest_id
        with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
            response = client.post(
                self._url("/session/start"),
                json=payload if payload else {},
            )
            response.raise_for_status()
            return response.json()

    def chat_stream(
        self,
        session_id: str,
        message: str,
        *,
        display_message: str | None = None,
        silent_response: bool = False,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        guest_id: str | None = None,
    ) -> Iterator[str]:
        payload: dict[str, Any] = {
            "session_id": session_id,
            "message": message,
            "silent_response": silent_response,
        }
        if display_message is not None:
            payload["display_message"] = display_message
        if metadata is not None:
            payload["metadata"] = metadata
        if user_id is not None:
            payload["user_id"] = user_id
        if guest_id is not None:
            payload["guest_id"] = guest_id

        with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
            with client.stream("POST", self._url("/chat/stream"), json=payload) as response:
                response.raise_for_status()
                for chunk in response.iter_text():
                    if chunk:
                        yield chunk

    def get_history(self, session_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
            response = client.get(self._url(f"/session/{session_id}/history"))
            response.raise_for_status()
            return response.json()

    def save_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        display_content: str | None = None,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        guest_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": role, "content": content}
        if display_content is not None:
            payload["display_content"] = display_content
        if metadata is not None:
            payload["metadata"] = metadata
        if user_id is not None:
            payload["user_id"] = user_id
        if guest_id is not None:
            payload["guest_id"] = guest_id

        with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
            response = client.post(self._url(f"/session/{session_id}/message"), json=payload)
            response.raise_for_status()
            return response.json()

    def get_profile(self, owner_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
            response = client.get(self._url(f"/learner/{owner_id}/profile"))
            response.raise_for_status()
            return response.json()

    def list_sessions(self, owner_id: str, *, limit: int = 50) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
            response = client.get(
                self._url(f"/learner/{owner_id}/sessions"),
                params={"limit": limit},
            )
            response.raise_for_status()
            return response.json()

    def ingest(
        self,
        *,
        file_path: str | None = None,
        url: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Ingest a local file or a URL into the knowledge base (exactly one source)."""
        if bool(file_path) == bool(url):
            raise ValueError("Provide exactly one of file_path or url")

        with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
            if file_path:
                with open(file_path, "rb") as fh:
                    response = client.post(
                        self._url("/ingest"),
                        files={"file": (file_path.split("\\")[-1].split("/")[-1], fh)},
                        data={"force": "true" if force else "false"},
                    )
            else:
                response = client.post(
                    self._url("/ingest"),
                    json={"url": url, "force": force},
                )
            response.raise_for_status()
            return response.json()
