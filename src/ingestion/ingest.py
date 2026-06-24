import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import psycopg2
from dotenv import load_dotenv

from src.config import configure_llama_index
from src.ingestion.pipeline import ingest_directory
from src.ingestion.vector_store import get_db_params, get_vector_table_name

load_dotenv()
configure_llama_index()

SUPABASE_VARS = [
    "SUPABASE_HOST",
    "SUPABASE_PORT",
    "SUPABASE_DATABASE",
    "SUPABASE_USER",
    "SUPABASE_PASSWORD",
]


def _validate_supabase_env() -> None:
    missing = [var for var in SUPABASE_VARS if not os.getenv(var)]
    if missing:
        raise RuntimeError(
            f"Missing required Supabase environment variables: {', '.join(missing)}"
        )


def ingest_documents(incremental: bool = True, remove_stale: bool = True):
    print("Starting document ingestion pipeline...")
    summary = ingest_directory("data", incremental=incremental, remove_stale=remove_stale)

    print(f"Indexed: {len(summary.indexed)} source(s), {summary.total_chunks} chunk(s)")
    for item in summary.indexed:
        print(f"  + {item.source_path} ({item.chunk_count} chunks)")

    if summary.skipped:
        print(f"Skipped unchanged: {len(summary.skipped)} source(s)")

    if summary.deleted:
        print(f"Removed stale: {len(summary.deleted)} source(s)")
        for item in summary.deleted:
            print(f"  - {item.source_path}")

    if summary.failed:
        print(f"Failed: {len(summary.failed)} source(s)")
        for item in summary.failed:
            print(f"  ! {item.source_path}: {item.message}")

    db_type = "Supabase" if os.getenv("USE_SUPABASE", "false").lower() == "true" else "local"
    print(f"Ingestion complete. Documents are searchable in {db_type} PostgreSQL.")

    if os.getenv("USE_SUPABASE", "false").lower() == "true":
        conn = psycopg2.connect(**get_db_params())
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {get_vector_table_name()}")
                count = cur.fetchone()[0]
            print(f"Verification: Found {count} vector records in Supabase database")
        finally:
            conn.close()

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into the vector store")
    parser.add_argument(
        "--supabase",
        action="store_true",
        help="Use Supabase credentials (sets USE_SUPABASE=true)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full re-ingest of all documents",
    )
    args = parser.parse_args()

    if args.supabase:
        os.environ["USE_SUPABASE"] = "true"
        _validate_supabase_env()

    if not os.path.exists("data"):
        print("Error: 'data' directory not found. Please create it and add your documents.")
        sys.exit(1)

    ingest_documents(incremental=not args.full)