import logging

from psycopg2.extensions import connection as PgConnection

from src.db.connection import db_label, get_connection
from src.db.vector_config import get_vector_table_name
from src.ingestion.registry import REGISTRY_TABLE

logger = logging.getLogger(__name__)

LEGACY_VECTOR_TABLES = ("data_data_vectors", "data_data_data_vectors")


def _table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) AS regclass", (f"public.{table_name}",))
    row = cur.fetchone()
    if not row:
        return False
    value = row["regclass"] if isinstance(row, dict) else row[0]
    return value is not None


def _drop_if_exists(cur, table_name: str) -> None:
    if _table_exists(cur, table_name):
        cur.execute(f"DROP TABLE {table_name} CASCADE")
        logger.info("Dropped %s", table_name)


def wipe_ingestion_data(*, include_chat: bool = False) -> dict[str, int | str]:
    """
    Remove all vector chunks and ingestion registry entries.
    Optionally clear chat history as well.
    """
    from src.chatbot.retrieval_cache import clear_retrieval_caches as clear_bm25_cache

    vector_table = get_vector_table_name()
    tables_to_clear = {vector_table, *LEGACY_VECTOR_TABLES, REGISTRY_TABLE}
    if include_chat:
        tables_to_clear.add("chat_messages")

    cleared: dict[str, int | str] = {"backend": db_label()}

    conn: PgConnection = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            for table in LEGACY_VECTOR_TABLES:
                if _table_exists(cur, table):
                    _drop_if_exists(cur, table)
                    cleared[table] = "dropped"

            for table in tables_to_clear:
                if table in LEGACY_VECTOR_TABLES:
                    continue
                if not _table_exists(cur, table):
                    continue
                cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                cleared[table] = 0
                logger.info("Truncated %s", table)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    clear_bm25_cache()
    return cleared