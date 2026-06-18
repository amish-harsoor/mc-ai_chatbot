import psycopg2
from psycopg2.extras import DictCursor
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
    """Create the chat_messages table if it doesn't exist."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
            """)
        conn.commit()
    finally:
        conn.close()

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

def get_session_history_raw(session_id: str) -> list[dict]:
    """Retrieve all messages for a given session as raw dictionaries."""
    conn = get_db_connection()
    messages = []
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT role, content, created_at 
                FROM chat_messages 
                WHERE session_id = %s 
                ORDER BY created_at ASC
            """, (session_id,))
            rows = cur.fetchall()
            
            for row in rows:
                messages.append({
                    "role": row['role'],
                    "content": row['content'],
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None
                })
    finally:
        conn.close()
    
    return messages

def save_message(session_id: str, role: str, content: str):
    """Save a single message to the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_messages (session_id, role, content)
                VALUES (%s, %s, %s)
            """, (session_id, role, content))
        conn.commit()
    finally:
        conn.close()
