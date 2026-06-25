import logging
import os

from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.postgres import PGVectorStore

from src.db.connection import get_connection
from src.db.vector_config import get_db_params, get_pgvector_store_name, get_vector_table_name

logger = logging.getLogger(__name__)

EMBED_DIM = int(os.getenv("EMBED_DIM", "384"))
REQUIRED_VECTOR_COLUMNS = frozenset({"id", "text", "metadata_", "node_id", "embedding"})


def _vector_table_schema_ok(cur, table_name: str) -> bool:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    columns = {row[0] for row in cur.fetchall()}
    return REQUIRED_VECTOR_COLUMNS.issubset(columns)


def ensure_vector_table_schema() -> None:
    """Drop legacy/incompatible vector tables so LlamaIndex can create data_vectors."""
    table = get_vector_table_name()
    with get_connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
            exists = cur.fetchone()[0] is not None
            if not exists:
                return
            if _vector_table_schema_ok(cur, table):
                return
            logger.warning(
                "Dropping incompatible vector table %s (expected LlamaIndex columns: %s)",
                table,
                ", ".join(sorted(REQUIRED_VECTOR_COLUMNS)),
            )
            cur.execute(f"DROP TABLE {table} CASCADE")


def create_vector_store() -> PGVectorStore:
    ensure_vector_table_schema()
    params = get_db_params()
    store = PGVectorStore.from_params(
        **params,
        table_name=get_pgvector_store_name(),
        embed_dim=EMBED_DIM,
    )
    store._initialize()
    return store


def load_index() -> VectorStoreIndex:
    return VectorStoreIndex.from_vector_store(create_vector_store())