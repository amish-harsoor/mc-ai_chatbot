"""
Unified database bootstrap for Supabase or local PostgreSQL.

Creates pgvector extension, chat tables, ingestion registry, and verifies vector storage.
"""

import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv

from src.db.connection import db_label, get_connection
from src.db.status import print_ingestion_status
from src.db.vector_config import use_supabase, validate_db_env
from src.ingestion.registry import DocumentRegistry
from src.ingestion.vector_store import create_vector_store
from src.db.course_prices import init_course_prices_table
from src.db.session_manager import init_db

load_dotenv()


def ensure_pgvector() -> None:
    with get_connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    print("pgvector extension ready.")


def ensure_vector_store() -> None:
    create_vector_store()
    print("Vector store schema verified.")


def init_database(*, configure_embeddings: bool = False) -> bool:
    if configure_embeddings:
        from src.config import configure_llama_index

        configure_llama_index()

    print(f"Initializing {db_label()} database...")
    validate_db_env()
    ensure_pgvector()
    init_db()
    print("chat_messages, chat_sessions, and learner_profiles tables ready.")
    init_course_prices_table()
    print("course_prices table ready.")
    DocumentRegistry()
    print("ingestion_registry table ready.")
    ensure_vector_store()
    print("Database initialization complete.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize database schema for the chatbot")
    parser.add_argument(
        "--supabase",
        action="store_true",
        help="Use Supabase credentials (sets USE_SUPABASE=true)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local DB_* credentials (sets USE_SUPABASE=false)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print ingestion status after init",
    )
    args = parser.parse_args()

    if args.local:
        os.environ["USE_SUPABASE"] = "false"
    elif args.supabase or use_supabase():
        os.environ["USE_SUPABASE"] = "true"

    validate_db_env()
    init_database(configure_embeddings=True)
    if args.status:
        print()
        print_ingestion_status()