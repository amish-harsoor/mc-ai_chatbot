import psycopg2

from src.db.vector_config import get_db_params, use_supabase


def get_connection():
    """Single Postgres connection for chat, vectors, and ingestion registry."""
    return psycopg2.connect(**get_db_params())


def db_label() -> str:
    return "Supabase" if use_supabase() else "local PostgreSQL"