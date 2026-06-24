from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.postgres import PGVectorStore

from src.db.vector_config import get_db_params, get_vector_table_name

EMBED_DIM = 384


def create_vector_store() -> PGVectorStore:
    params = get_db_params()
    return PGVectorStore.from_params(
        **params,
        table_name=get_vector_table_name(),
        embed_dim=EMBED_DIM,
    )


def load_index() -> VectorStoreIndex:
    return VectorStoreIndex.from_vector_store(create_vector_store())