import logging
from contextlib import asynccontextmanager
from typing import Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.router import router
from src.api.settings import api_key, api_prefix

logger = logging.getLogger("mc_ai_chatbot")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Optional shared-secret gate when CHATBOT_API_KEY is set."""

    def __init__(self, app, required_key: str, prefix: str = ""):
        super().__init__(app)
        self.required_key = required_key
        self.health_paths = {"/health", f"{prefix}/health" if prefix else "/health"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.health_paths:
            return await call_next(request)

        provided = request.headers.get("X-API-Key", "")
        if provided != self.required_key:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
        return await call_next(request)


async def startup_chatbot() -> None:
    """Initialize LLM config, DB tables, and the vector index. Safe to call multiple times."""
    from src.config import configure_llama_index

    try:
        configure_llama_index()
    except Exception as e:
        logger.error(f"LLM/embeddings configuration failed: {e}")

    from src.db.course_prices import init_course_prices_table
    from src.db.session_manager import init_db

    try:
        init_db()
        init_course_prices_table()
        logger.info("chat_messages, sessions/profiles, and course_prices tables initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    from src.chatbot.chatbot import init_chatbot

    try:
        init_chatbot()
    except Exception as e:
        logger.error(f"Chatbot index initialization failed: {e}")


async def shutdown_chatbot() -> None:
    from src.chatbot.chatbot import clear_session_engine_cache
    from src.chatbot.retrieval import clear_retrieval_caches

    clear_session_engine_cache()
    clear_retrieval_caches()
    logger.info("Session and retrieval caches cleared on shutdown")


def create_app(
    *,
    prefix: str | None = None,
    cors_origins: Sequence[str] | None = None,
    enable_api_key: bool | None = None,
    title: str = "Course Chatbot API",
) -> FastAPI:
    """
    Factory for the chatbot FastAPI application.

    Standalone:
        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=8000)

    Mount into another FastAPI app:
        from src.api.router import router
        from src.api.app import startup_chatbot, shutdown_chatbot

        host = FastAPI()
        host.include_router(router, prefix="/api/v1/chatbot")

        @host.on_event("startup")
        async def _init():
            await startup_chatbot()

        @host.on_event("shutdown")
        async def _cleanup():
            await shutdown_chatbot()
    """
    resolved_prefix = api_prefix() if prefix is None else prefix.rstrip("/")
    if resolved_prefix and not resolved_prefix.startswith("/"):
        resolved_prefix = f"/{resolved_prefix}"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await startup_chatbot()
        yield
        await shutdown_chatbot()

    application = FastAPI(title=title, lifespan=lifespan)
    application.include_router(router, prefix=resolved_prefix)

    origins = list(cors_origins) if cors_origins is not None else ["*"]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    key = api_key()
    use_key = enable_api_key if enable_api_key is not None else bool(key)
    if use_key and key:
        application.add_middleware(APIKeyMiddleware, required_key=key, prefix=resolved_prefix)

    return application