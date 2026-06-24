import psycopg2
from psycopg2.extras import DictCursor, Json
import os
import json
from dotenv import load_dotenv
from llama_index.core.llms import ChatMessage, MessageRole

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("SUPABASE_HOST"),
        port=os.getenv("SUPABASE_PORT", "5432"),
        database=os.getenv("SUPABASE_DATABASE", "postgres"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD")
    )

def init_db():
    """Create the chat_messages table and ensure display/metadata columns exist."""
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

_SCRIPTED_ONBOARDING_STEPS = frozenset({"welcome", "experience", "department", "goal"})


def should_include_in_llm_history(role: str, metadata: dict | None) -> bool:
    """Return False for onboarding KV pairs and scripted bot prompts."""
    metadata = metadata or {}

    if metadata.get("type") == "onboarding_selection":
        return False

    if role == "user" and metadata.get("step") in ("experience", "department"):
        return False

    if role == "assistant":
        if metadata.get("type") == "onboarding":
            return False
        if metadata.get("step") in _SCRIPTED_ONBOARDING_STEPS:
            return False
        if metadata.get("visible") is False:
            return False

    return True


def get_session_history(session_id: str) -> list[ChatMessage]:
    """Retrieve all messages for a given session, formatted for LlamaIndex."""
    conn = get_db_connection()
    messages = []
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT role, content 
                FROM chat_messages 
                WHERE session_id = %s 
                ORDER BY created_at ASC
            """, (session_id,))
            rows = cur.fetchall()
            
            for row in rows:
                role = MessageRole.USER if row['role'] == 'user' else MessageRole.ASSISTANT
                messages.append(ChatMessage(role=role, content=row['content']))
    finally:
        conn.close()
    
    return messages


def get_llm_session_history(session_id: str) -> list[ChatMessage]:
    """Session history for the LLM, excluding onboarding selections and scripted prompts."""
    conn = get_db_connection()
    messages = []
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT role, content, metadata
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
            """, (session_id,))
            rows = cur.fetchall()

            for row in rows:
                metadata = _normalize_metadata(row["metadata"])
                if not should_include_in_llm_history(row["role"], metadata):
                    continue
                role = MessageRole.USER if row["role"] == "user" else MessageRole.ASSISTANT
                messages.append(ChatMessage(role=role, content=row["content"]))
    finally:
        conn.close()

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
):
    """Save a single message to the database."""
    if display_content is None:
        display_content = content

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_messages (session_id, role, content, display_content, metadata)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                session_id,
                role,
                content,
                display_content,
                Json(metadata) if metadata is not None else None,
            ))
        conn.commit()
    finally:
        conn.close()