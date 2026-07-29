from psycopg2.extras import DictCursor, Json
import json
import os
from typing import Any

from dotenv import load_dotenv
from llama_index.core.llms import ChatMessage, MessageRole

from src.db.connection import get_connection

load_dotenv()

# Cap rows fed into the LLM memory buffer (after onboarding filters).
LLM_HISTORY_MAX_MESSAGES = max(1, int(os.getenv("LLM_HISTORY_MAX_MESSAGES", "24")))


def get_db_connection():
    return get_connection()


def init_db():
    """Create chat_messages plus guest/registered session + profile tables."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    display_content TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
            """)
            cur.execute("""
                ALTER TABLE chat_messages
                ADD COLUMN IF NOT EXISTS display_content TEXT;
            """)
            cur.execute("""
                ALTER TABLE chat_messages
                ADD COLUMN IF NOT EXISTS metadata JSONB;
            """)
        conn.commit()
    finally:
        conn.close()

    from src.db.profiles import init_profile_tables

    init_profile_tables()


_SCRIPTED_ONBOARDING_STEPS = frozenset({"welcome", "experience", "department", "goal"})


def should_include_in_llm_history(role: str, metadata: dict | None) -> bool:
    """Return False for onboarding KV pairs and scripted bot prompts."""
    metadata = metadata or {}

    if metadata.get("visible") is False:
        return False

    if metadata.get("type") in ("onboarding_selection", "preference_update"):
        return False

    if role == "user" and metadata.get("step") in ("experience", "department"):
        return False

    if role == "assistant":
        if metadata.get("type") == "onboarding":
            return False
        if metadata.get("step") in _SCRIPTED_ONBOARDING_STEPS:
            return False

    return True


def get_llm_session_history(
    session_id: str,
    *,
    max_messages: int | None = None,
) -> list[ChatMessage]:
    """Session history for the LLM, excluding onboarding selections and scripted prompts.

    Loads only a recent window from the DB (not the full transcript) to keep free-chat
    turns light as sessions grow.
    """
    limit = max_messages if max_messages is not None else LLM_HISTORY_MAX_MESSAGES
    # Over-fetch raw rows so filtered onboarding noise does not empty the window.
    fetch_limit = max(limit * 4, limit)

    conn = get_db_connection()
    messages: list[ChatMessage] = []
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                SELECT role, content, metadata
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (session_id, fetch_limit),
            )
            rows = list(reversed(cur.fetchall()))

            for row in rows:
                metadata = _normalize_metadata(row["metadata"])
                if not should_include_in_llm_history(row["role"], metadata):
                    continue
                role = MessageRole.USER if row["role"] == "user" else MessageRole.ASSISTANT
                messages.append(ChatMessage(role=role, content=row["content"]))
    finally:
        conn.close()

    if len(messages) > limit:
        messages = messages[-limit:]
    return messages


def _normalize_metadata(raw_metadata) -> dict | None:
    if raw_metadata is None:
        return None
    if isinstance(raw_metadata, dict):
        return raw_metadata
    if isinstance(raw_metadata, str):
        try:
            return json.loads(raw_metadata)
        except json.JSONDecodeError:
            return None
    return None


def get_session_history_raw(session_id: str) -> list[dict]:
    """Retrieve all messages for a given session as raw dictionaries."""
    conn = get_db_connection()
    messages = []
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT role, content, display_content, metadata, created_at
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
            """, (session_id,))
            rows = cur.fetchall()

            for row in rows:
                metadata = _normalize_metadata(row['metadata'])
                messages.append({
                    "role": row['role'],
                    "content": row['content'],
                    "display_content": row['display_content'] or row['content'],
                    "metadata": metadata,
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None
                })
    finally:
        conn.close()

    return messages


def save_message(
    session_id: str,
    role: str,
    content: str,
    display_content: str | None = None,
    metadata: dict | None = None,
    *,
    user_id: str | None = None,
    guest_id: str | None = None,
):
    """
    Persist a full chat message (always) and update condensed session/profile snapshots.

    Full text goes to chat_messages for history + future recommendation features.
    Condensed prefs/stats go to chat_sessions + learner_profiles.
    """
    save_messages(
        session_id,
        [
            {
                "role": role,
                "content": content,
                "display_content": display_content,
                "metadata": metadata,
            }
        ],
        user_id=user_id,
        guest_id=guest_id,
    )


def save_messages(
    session_id: str,
    messages: list[dict[str, Any]],
    *,
    user_id: str | None = None,
    guest_id: str | None = None,
) -> None:
    """Insert one or more chat_messages in a single transaction, then update snapshots."""
    if not messages:
        return

    rows: list[tuple] = []
    for message in messages:
        role = message["role"]
        content = message["content"]
        display_content = message.get("display_content")
        if display_content is None:
            display_content = content
        metadata = message.get("metadata")
        rows.append(
            (
                session_id,
                role,
                content,
                display_content,
                Json(metadata) if metadata is not None else None,
            )
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO chat_messages (session_id, role, content, display_content, metadata)
                VALUES (%s, %s, %s, %s, %s)
                """,
                rows,
            )
        conn.commit()
    finally:
        conn.close()

    try:
        from src.db.profiles import record_message

        for message in messages:
            display_content = message.get("display_content")
            if display_content is None:
                display_content = message["content"]
            record_message(
                session_id,
                role=message["role"],
                content=display_content,
                metadata=message.get("metadata"),
                user_id=user_id,
                guest_id=guest_id,
            )
    except Exception:
        # Primary message write already committed; snapshot is best-effort
        pass
