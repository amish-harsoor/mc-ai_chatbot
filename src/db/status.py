from psycopg2.extras import RealDictCursor

from src.db.connection import db_label, get_connection
from src.db.vector_config import get_vector_table_name
from src.ingestion.registry import REGISTRY_TABLE


def _table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) AS regclass", (f"public.{table_name}",))
    row = cur.fetchone()
    if not row:
        return False
    if isinstance(row, dict):
        value = row.get("regclass") or row.get(0)
    else:
        value = row[0]
    return value is not None


def get_ingestion_status() -> dict:
    vector_table = get_vector_table_name()
    status = {
        "backend": db_label(),
        "vector_table": vector_table,
        "vector_count": 0,
        "registry_count": 0,
        "chat_message_count": 0,
        "sources": [],
    }

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if _table_exists(cur, vector_table):
                cur.execute(f"SELECT COUNT(*) AS count FROM {vector_table}")
                status["vector_count"] = cur.fetchone()["count"]

            if _table_exists(cur, REGISTRY_TABLE):
                cur.execute(f"SELECT COUNT(*) AS count FROM {REGISTRY_TABLE}")
                status["registry_count"] = cur.fetchone()["count"]
                cur.execute(
                    f"""
                    SELECT source_path, source_type, chunk_count, updated_at
                    FROM {REGISTRY_TABLE}
                    ORDER BY updated_at DESC
                    LIMIT 20
                    """
                )
                status["sources"] = [dict(row) for row in cur.fetchall()]

            if _table_exists(cur, "chat_messages"):
                cur.execute("SELECT COUNT(*) AS count FROM chat_messages")
                status["chat_message_count"] = cur.fetchone()["count"]

    return status


def print_ingestion_status() -> dict:
    status = get_ingestion_status()
    print(f"Backend: {status['backend']}")
    print(f"Vector table: {status['vector_table']} ({status['vector_count']} rows)")
    print(f"Ingestion registry: {status['registry_count']} source(s)")
    print(f"Chat messages: {status['chat_message_count']} row(s)")

    if status["sources"]:
        print("\nRecent sources:")
        for row in status["sources"]:
            updated = row.get("updated_at")
            stamp = updated.isoformat() if updated else "unknown"
            print(
                f"  - {row['source_path']} "
                f"[{row['source_type']}, {row['chunk_count']} chunks, {stamp}]"
            )
    else:
        print("\nNo indexed sources in registry.")

    return status