"""
HTTP route package — one endpoint per responsibility.

  health.py    — GET  /health
  sessions.py  — session start / history / persist message
  chat.py      — POST /chat/stream
  ingest.py    — POST /ingest
  learners.py  — learner profile / session list

    from src.api.router import router
"""

from fastapi import APIRouter

from src.api.router import chat, health, ingest, learners, sessions

# No parent tags — each domain router sets exactly one tag so OpenAPI/Swagger
# does not list the same path twice under "chatbot" and e.g. "chat".
router = APIRouter()
router.include_router(health.router)
router.include_router(sessions.router)
router.include_router(chat.router)
router.include_router(ingest.router)
router.include_router(learners.router)

__all__ = ["router"]
