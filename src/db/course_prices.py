import logging

from psycopg2.extras import RealDictCursor, execute_values

from src.db.connection import get_connection

logger = logging.getLogger(__name__)

COURSE_PRICES_TABLE = "course_prices"


def init_course_prices_table() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {COURSE_PRICES_TABLE} (
                    course_id VARCHAR(10) PRIMARY KEY,
                    price TEXT NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{COURSE_PRICES_TABLE}_updated_at
                ON {COURSE_PRICES_TABLE}(updated_at)
                """
            )
        conn.commit()


def load_price_catalog_from_db() -> dict[str, str]:
    init_course_prices_table()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT course_id, price FROM {COURSE_PRICES_TABLE} ORDER BY course_id"
            )
            rows = cur.fetchall()
    return {str(row["course_id"]): str(row["price"]) for row in rows}


def upsert_price_catalog_to_db(catalog: dict[str, str]) -> int:
    if not catalog:
        return 0

    init_course_prices_table()
    values = [(str(course_id), str(price)) for course_id, price in catalog.items()]

    with get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {COURSE_PRICES_TABLE} (course_id, price, updated_at)
                VALUES %s
                ON CONFLICT (course_id) DO UPDATE SET
                    price = EXCLUDED.price,
                    updated_at = NOW()
                """,
                values,
                template="(%s, %s, NOW())",
            )
        conn.commit()

    logger.info("Upserted %s course prices to %s", len(values), COURSE_PRICES_TABLE)
    return len(values)


def replace_price_catalog_in_db(catalog: dict[str, str]) -> int:
    """Wipe course_prices and insert catalog only (no leftover false GSA rows)."""
    init_course_prices_table()
    values = [(str(course_id), str(price)) for course_id, price in catalog.items()]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {COURSE_PRICES_TABLE}")
            if values:
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {COURSE_PRICES_TABLE} (course_id, price, updated_at)
                    VALUES %s
                    """,
                    values,
                    template="(%s, %s, NOW())",
                )
        conn.commit()

    logger.info(
        "Replaced %s with %s official course prices",
        COURSE_PRICES_TABLE,
        len(values),
    )
    return len(values)
