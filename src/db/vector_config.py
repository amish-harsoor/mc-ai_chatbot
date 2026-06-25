import os


def use_supabase() -> bool:
    return os.getenv("USE_SUPABASE", "true").lower() == "true"


def get_pgvector_store_name() -> str:
    """Logical name passed to LlamaIndex PGVectorStore (physical table is data_{name})."""
    return "vectors"


def get_vector_table_name() -> str:
    """Physical Postgres table holding embeddings (for BM25 SQL, status, wipe)."""
    return f"data_{get_pgvector_store_name()}"


def get_db_params() -> dict:
    if use_supabase():
        return {
            "host": os.getenv("SUPABASE_HOST", "localhost"),
            "port": int(os.getenv("SUPABASE_PORT", "5432")),
            "database": os.getenv("SUPABASE_DATABASE", "postgres"),
            "user": os.getenv("SUPABASE_USER", "postgres"),
            "password": os.getenv("SUPABASE_PASSWORD"),
        }
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "database": os.getenv("DB_NAME", "mc_chatbot"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD"),
    }


def validate_db_env() -> None:
    if use_supabase():
        required = [
            "SUPABASE_HOST",
            "SUPABASE_USER",
            "SUPABASE_PASSWORD",
        ]
        prefix = "SUPABASE"
    else:
        required = [
            "DB_HOST",
            "DB_USER",
            "DB_PASSWORD",
            "DB_NAME",
        ]
        prefix = "DB"

    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            f"Missing required {prefix} environment variables: {', '.join(missing)}"
        )