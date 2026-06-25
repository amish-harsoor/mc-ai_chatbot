import os


def api_prefix() -> str:
    """URL prefix for all chatbot routes (e.g. '/api/v1/chatbot'). No trailing slash."""
    raw = os.getenv("CHATBOT_API_PREFIX", os.getenv("API_PREFIX", "")).strip()
    if not raw:
        return ""
    return raw if raw.startswith("/") else f"/{raw}"


def api_key() -> str | None:
    """Optional shared secret; clients send X-API-Key when set."""
    key = os.getenv("CHATBOT_API_KEY", os.getenv("API_KEY", "")).strip()
    return key or None