import os

from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.postgres import PGVectorStore

EMBED_DIM = 384


def use_supabase() -> bool:
    return os.getenv("USE_SUPABASE", "false").lower() == "true"


def get_vector_table_name() -> str:
    return "data_data_vectors" if use_supabase() else "data_vectors"


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


def create_vector_store() -> PGVectorStore:
    params = get_db_params()
    return PGVectorStore.from_params(
        **params,
        table_name=get_vector_table_name(),
        embed_dim=EMBED_DIM,
    )


def load_index() -> VectorStoreIndex:
    return VectorStoreIndex.from_vector_store(create_vector_store())