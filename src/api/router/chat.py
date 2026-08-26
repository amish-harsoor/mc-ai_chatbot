"""Streaming chat — generate a bot reply for one user message."""

from __future__ import annotations

import logging
from typing import Any, Iterable
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.api.router.deps import require_session_uuid, resolve_request_owner
from src.api.schemas import ChatRequest
from src.chatbot.chatbot import get_or_create_chat_engine

logger = logging.getLogger("mc_ai_chatbot")

router = APIRouter(tags=["chat"])

# Exposed to browsers so the widget can read structured options without text heuristics.
_OPTIONS_HEADER = "X-MC-Options"


def _linkify_course_ids(text: str) -> str:
    """Normalize course cards: plain titles + a single Register Now CTA each."""
    from src.chatbot.course_cards import normalize_course_markdown

    return normalize_course_markdown(text)


def _options_header_value(options: list[str] | None) -> str | None:
    if not options:
        return None
    # Pipe-separated, URL-encoded so commas/spaces in labels stay intact.
    return "|".join(quote(str(opt), safe="") for opt in options if str(opt).strip())


def _stream_reply(
    body: Iterable[str],
    *,
    options: list[str] | None = None,
) -> StreamingResponse:
    headers: dict[str, str] = {}
    encoded = _options_header_value(options)
    if encoded:
        headers[_OPTIONS_HEADER] = encoded
        headers["Access-Control-Expose-Headers"] = _OPTIONS_HEADER
    return StreamingResponse(body, media_type="text/plain", headers=headers or None)


def _save_turn(
    session_id: str,
    *,
    user_message: str,
    user_display: str,
    user_metadata: dict[str, Any] | None,
    assistant_message: str,
    assistant_metadata: dict[str, Any] | None,
    user_id: str | None,
    guest_id: str | None,
) -> None:
    from src.db.session_manager import save_messages

    save_messages(
        session_id,
        [
            {
                "role": "user",
                "content": user_message,
                "display_content": user_display,
                "metadata": user_metadata,
            },
            {
                "role": "assistant",
                "content": assistant_message,
                "display_content": assistant_message,
                "metadata": assistant_metadata,
            },
        ],
        user_id=user_id,
        guest_id=guest_id,
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Produce an assistant reply for a user message (support, out-of-domain, or RAG).

    Always returns a streamed reply. To persist a message without a bot response
    (onboarding UI, welcome copy), use ``POST /session/{id}/message`` instead.
    """
    from src.chatbot.query_context import enrich_metadata_with_durable_profile
    from src.db.session_manager import get_llm_session_history

    require_session_uuid(request.session_id)

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    user_id, guest_id = resolve_request_owner(
        user_id=request.user_id,
        guest_id=request.guest_id,
        session_id=request.session_id,
    )
    display_message = request.display_message or request.message

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

        assistant_metadata: dict[str, Any] = {
            "visible": not request.silent_response,
            "type": "support",
        }
        if kind:
            assistant_metadata["support_kind"] = kind
        options = support_options_for_message(request.message)
        if options:
            assistant_metadata["options"] = options

        def support_generator():
            _save_turn(
                request.session_id,
                user_message=request.message,
                user_display=display_message,
                user_metadata=user_metadata or None,
                assistant_message=reply,
                assistant_metadata=assistant_metadata,
                user_id=user_id,
                guest_id=guest_id,
            )
            yield reply

        return _stream_reply(support_generator(), options=options)

    # Clearly non-training topics (cooking, sports, etc.) → fixed reply, skip RAG latency.
    if is_out_of_domain_message(request.message, metadata=request.metadata):
        reply = out_of_domain_reply()
        user_metadata = dict(request.metadata) if request.metadata else {}
        user_metadata.setdefault("type", "out_of_domain")

        def ood_generator():
            _save_turn(
                request.session_id,
                user_message=request.message,
                user_display=display_message,
                user_metadata=user_metadata or None,
                assistant_message=reply,
                assistant_metadata={
                    "visible": not request.silent_response,
                    "type": "out_of_domain",
                },
                user_id=user_id,
                guest_id=guest_id,
            )
            yield reply

        return _stream_reply(ood_generator())

    # Single-course fact questions ("cost of course 4606") → catalog JSON only (no LLM).
    from src.chatbot.catalog_lookup import (
        build_catalog_lookup_reply,
        should_use_catalog_lookup,
    )

    if should_use_catalog_lookup(request.message, metadata=request.metadata):
        reply = build_catalog_lookup_reply(request.message)
        if reply:
            reply = _linkify_course_ids(reply)
            user_metadata = dict(request.metadata) if request.metadata else {}
            user_metadata.setdefault("type", "catalog_lookup")

            def catalog_generator():
                _save_turn(
                    request.session_id,
                    user_message=request.message,
                    user_display=display_message,
                    user_metadata=user_metadata or None,
                    assistant_message=reply,
                    assistant_metadata={
                        "visible": not request.silent_response,
                        "type": "catalog_lookup",
                        "template": True,
                    },
                    user_id=user_id,
                    guest_id=guest_id,
                )
                yield reply

            return _stream_reply(catalog_generator())

    # Fill missing prefs from durable session/profile before template recs or RAG.
    enriched_metadata = enrich_metadata_with_durable_profile(
        request.metadata,
        session_id=request.session_id,
        user_id=user_id,
        guest_id=guest_id,
    )

    # Profile-complete onboarding / goal refresh → retrieve + template (no LLM).
    from src.chatbot.recommendations import (
        build_template_recommendation_reply,
        should_use_template_recommendations,
    )

    if should_use_template_recommendations(
        enriched_metadata, latest_message=request.message
    ):
        try:
            reply = build_template_recommendation_reply(
                latest_message=request.message,
                request_metadata=enriched_metadata,
            )
        except Exception as e:
            logger.error(
                "Template profile recommendations failed; falling back to LLM: %s",
                e,
                exc_info=True,
            )
        else:
            reply = _linkify_course_ids(reply)
            user_metadata = dict(enriched_metadata) if enriched_metadata else {}
            user_metadata.setdefault("type", "profile_recommendation")

            def template_generator():
                _save_turn(
                    request.session_id,
                    user_message=request.message,
                    user_display=display_message,
                    user_metadata=user_metadata or None,
                    assistant_message=reply,
                    assistant_metadata={
                        "visible": not request.silent_response,
                        "type": "profile_recommendation",
                        "template": True,
                    },
                    user_id=user_id,
                    guest_id=guest_id,
                )
                yield reply

            return _stream_reply(template_generator())

    chat_history = get_llm_session_history(request.session_id)
    chat_engine = get_or_create_chat_engine(
        request.session_id,
        chat_history,
        latest_message=request.message,
        request_metadata=enriched_metadata,
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
        raw_response = ""
        try:
            for token in streaming_response.response_gen:
                buffer += token
                raw_response += token

                # Flush mid-stream for UX; final persisted text is normalized once below.
                if len(buffer) > 100:
                    split_idx = buffer.rfind(" ", 0, len(buffer) - 50)
                    if split_idx == -1:
                        split_idx = len(buffer) - 50
                    yield buffer[:split_idx]
                    buffer = buffer[split_idx:]

            if buffer:
                yield buffer

            if not raw_response.strip():
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
                raw_response = fallback

            # Persist the same cleaned markdown the catalog/template paths store.
            full_response = _linkify_course_ids(raw_response)
            user_metadata = dict(enriched_metadata) if enriched_metadata else {}
            _save_turn(
                request.session_id,
                user_message=request.message,
                user_display=display_message,
                user_metadata=user_metadata or None,
                assistant_message=full_response,
                assistant_metadata={"visible": not request.silent_response},
                user_id=user_id,
                guest_id=guest_id,
            )
        except Exception as e:
            logger.error(f"Stream interrupted by model provider: {e}", exc_info=True)
            yield "\n\n[Error: AI Model provider disconnected. Please try again.]"

    return _stream_reply(response_generator())
