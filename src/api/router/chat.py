"""Streaming chat — generate a bot reply for one user message."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.api.router.deps import require_session_uuid, resolve_request_owner
from src.api.schemas import ChatRequest
from src.chatbot.chatbot import get_or_create_chat_engine

logger = logging.getLogger("mc_ai_chatbot")

router = APIRouter(tags=["chat"])

# Inject "Register Now" links after bold course IDs in streamed markdown.
_COURSE_ID_LINK_RE = re.compile(
    r"\*\*(\d+)\*\*(?!\s*\n\[Register Now\])",
)
_COURSE_ID_LINK_SUB = r"**\1**\n[Register Now](https://www.managementconcepts.com/product/\1)"


def _linkify_course_ids(text: str) -> str:
    return _COURSE_ID_LINK_RE.sub(_COURSE_ID_LINK_SUB, text)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Produce an assistant reply for a user message (support, out-of-domain, or RAG).

    Always returns a streamed reply. To persist a message without a bot response
    (onboarding UI, welcome copy), use ``POST /session/{id}/message`` instead.
    """
    from src.db.session_manager import get_llm_session_history, save_message

    require_session_uuid(request.session_id)

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    user_id, guest_id = resolve_request_owner(
        user_id=request.user_id,
        guest_id=request.guest_id,
        session_id=request.session_id,
    )

    # Non-course issues → fixed in-chat ticket reply (no RAG / LLM / page redirect).
    from src.chatbot.support import (
        classify_support_issue,
        is_out_of_domain_message,
        is_support_issue,
        out_of_domain_reply,
        support_options_for_message,
        support_reply_for_message,
    )

    if is_support_issue(request.message, metadata=request.metadata):
        reply = support_reply_for_message(request.message)
        kind = classify_support_issue(request.message, metadata=request.metadata)
        user_metadata = dict(request.metadata) if request.metadata else {}
        user_metadata.setdefault("type", "support_issue")
        if kind:
            user_metadata.setdefault("support_kind", kind)

        def support_generator():
            save_message(
                request.session_id,
                "user",
                request.message,
                display_content=request.display_message or request.message,
                metadata=user_metadata or None,
                user_id=user_id,
                guest_id=guest_id,
            )
            assistant_metadata: dict = {
                "visible": not request.silent_response,
                "type": "support",
            }
            if kind:
                assistant_metadata["support_kind"] = kind
            options = support_options_for_message(request.message)
            if options:
                assistant_metadata["options"] = options
            save_message(
                request.session_id,
                "assistant",
                reply,
                display_content=reply,
                metadata=assistant_metadata,
                user_id=user_id,
                guest_id=guest_id,
            )
            yield reply

        return StreamingResponse(support_generator(), media_type="text/plain")

    # Clearly non-training topics (cooking, sports, etc.) → fixed reply, skip RAG latency.
    if is_out_of_domain_message(request.message, metadata=request.metadata):
        reply = out_of_domain_reply()
        user_metadata = dict(request.metadata) if request.metadata else {}
        user_metadata.setdefault("type", "out_of_domain")

        def ood_generator():
            save_message(
                request.session_id,
                "user",
                request.message,
                display_content=request.display_message or request.message,
                metadata=user_metadata or None,
                user_id=user_id,
                guest_id=guest_id,
            )
            save_message(
                request.session_id,
                "assistant",
                reply,
                display_content=reply,
                metadata={
                    "visible": not request.silent_response,
                    "type": "out_of_domain",
                },
                user_id=user_id,
                guest_id=guest_id,
            )
            yield reply

        return StreamingResponse(ood_generator(), media_type="text/plain")

    chat_history = get_llm_session_history(request.session_id)
    chat_engine = get_or_create_chat_engine(
        request.session_id,
        chat_history,
        latest_message=request.message,
        request_metadata=request.metadata,
    )

    from src.chatbot.chatbot import get_streaming_response

    try:
        streaming_response = get_streaming_response(chat_engine, request.message)
    except Exception as e:
        logger.error(f"Error initiating chat stream with model provider: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="AI Model provider is currently unavailable. Please try again later.",
        )

    def response_generator():
        buffer = ""
        full_response = ""
        try:
            for token in streaming_response.response_gen:
                buffer += token
                full_response += token

                if len(buffer) > 100:
                    split_idx = buffer.rfind(" ", 0, len(buffer) - 50)
                    if split_idx == -1:
                        split_idx = len(buffer) - 50

                    chunk = buffer[:split_idx]
                    buffer = buffer[split_idx:]
                    yield _linkify_course_ids(chunk)

            if buffer:
                yield _linkify_course_ids(buffer)

            if not full_response.strip():
                if "career goal" in request.message.lower():
                    fallback = (
                        "I'm looking at our catalog right now, and we have excellent courses for that! "
                        "Could you specify if you prefer online or in-person training so I can narrow it down?"
                    )
                else:
                    fallback = (
                        "I'm here to help with courses from Management Concepts! "
                        "Please let me know what else you'd like to explore."
                    )
                yield fallback
                full_response = fallback

            user_metadata = dict(request.metadata) if request.metadata else {}
            save_message(
                request.session_id,
                "user",
                request.message,
                display_content=request.display_message or request.message,
                metadata=user_metadata or None,
                user_id=user_id,
                guest_id=guest_id,
            )
            assistant_metadata = {"visible": not request.silent_response}
            save_message(
                request.session_id,
                "assistant",
                full_response,
                display_content=full_response,
                metadata=assistant_metadata,
                user_id=user_id,
                guest_id=guest_id,
            )
        except Exception as e:
            logger.error(f"Stream interrupted by model provider: {e}", exc_info=True)
            yield "\n\n[Error: AI Model provider disconnected. Please try again.]"

    return StreamingResponse(response_generator(), media_type="text/plain")
