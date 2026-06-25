"""
Django view that proxies chat requests to the chatbot microservice.

Add to urls.py:
    path("api/chat/stream/", chat_stream_proxy),

Set CHATBOT_SERVICE_URL=http://localhost:8000 in Django settings or env.
"""

import os

import httpx
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json


CHATBOT_URL = os.getenv("CHATBOT_SERVICE_URL", "http://localhost:8000").rstrip("/")
CHATBOT_PREFIX = os.getenv("CHATBOT_API_PREFIX", "").rstrip("/")
CHATBOT_API_KEY = os.getenv("CHATBOT_API_KEY", "")


def _chatbot_url(path: str) -> str:
    prefix = CHATBOT_PREFIX if CHATBOT_PREFIX.startswith("/") else f"/{CHATBOT_PREFIX}" if CHATBOT_PREFIX else ""
    return f"{CHATBOT_URL}{prefix}{path}"


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if CHATBOT_API_KEY:
        headers["X-API-Key"] = CHATBOT_API_KEY
    return headers


@csrf_exempt
@require_POST
def chat_stream_proxy(request):
    body = json.loads(request.body)
    session_id = body.get("session_id", "")
    message = body.get("message", "")

    def stream():
        with httpx.Client(timeout=120.0) as client:
            with client.stream(
                "POST",
                _chatbot_url("/chat/stream"),
                json={"session_id": session_id, "message": message, **{k: v for k, v in body.items() if k not in ("session_id", "message")}},
                headers=_headers(),
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_text():
                    if chunk:
                        yield chunk

    return StreamingHttpResponse(stream(), content_type="text/plain")