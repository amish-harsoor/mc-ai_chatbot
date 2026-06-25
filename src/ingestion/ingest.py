import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv

load_dotenv()


def _early_preload_native_libs() -> None:
    """Load torch/onnx before other native libs — avoids Windows DLL init failures."""
    provider = os.getenv("EMBED_PROVIDER", "huggingface").lower()
    try:
        if provider == "huggingface":
            import torch  # noqa: F401
        elif provider == "fastembed":
            import onnxruntime  # noqa: F401
    except Exception:
        pass


_early_preload_native_libs()


def _configure_backend(args: argparse.Namespace) -> None:
    from src.db.vector_config import use_supabase, validate_db_env

    if args.local:
        os.environ["USE_SUPABASE"] = "false"
    elif args.supabase or use_supabase():
        os.environ["USE_SUPABASE"] = "true"
    validate_db_env()


def _print_summary(summary) -> None:
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


def ingest_from_directory(
    data_dir: str | Path,
    *,
    incremental: bool = True,
    remove_stale: bool = True,
) -> None:
    from src.ingestion.pipeline import ingest_directory

    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    print(f"Starting ingestion from {data_dir.resolve()}...")
    summary = ingest_directory(
        data_dir,
        incremental=incremental,
        remove_stale=remove_stale,
    )
    _print_summary(summary)


def ingest_single_file(path: str | Path, *, force: bool = False) -> None:
    from src.ingestion.pipeline import ingest_file as pipeline_ingest_file

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    print(f"Ingesting file {path.resolve()}...")
    result = pipeline_ingest_file(path, force=force)
    print(f"{result.action}: {result.source_path} ({result.chunk_count} chunks)")
    if result.message:
        print(f"  {result.message}")


def ingest_single_url(url: str, *, force: bool = False) -> None:
    from src.ingestion.pipeline import ingest_url as pipeline_ingest_url

    print(f"Ingesting URL {url}...")
    result = pipeline_ingest_url(url, force=force)
    print(f"{result.action}: {result.source_path} ({result.chunk_count} chunks)")
    if result.message:
        print(f"  {result.message}")


def ingest_url_list(path: str | Path, *, force: bool = False) -> None:
    from src.ingestion.pipeline import IngestionPipeline

    urls = [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not urls:
        raise ValueError(f"No URLs found in {path}")

    pipeline = IngestionPipeline()
    for url in urls:
        result = pipeline.ingest_url(url, force=force)
        print(f"{result.action}: {url} ({result.chunk_count} chunks)")


def main(argv: list[str] | None = None) -> int:
    default_dir = os.getenv("INGEST_DATA_DIR", "data")

    parser = argparse.ArgumentParser(description="Ingest documents into the vector store")
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
        "--dir",
        default=default_dir,
        help=f"Directory to scan for documents (default: {default_dir})",
    )
    parser.add_argument("--file", help="Ingest a single file")
    parser.add_argument("--url", help="Ingest a single URL")
    parser.add_argument("--urls", help="Text file with one URL per line")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full re-ingest of all documents in --dir",
    )
    parser.add_argument(
        "--low-memory",
        action="store_true",
        help="Use sentence chunking for PDFs/web and reduce per-file memory retention",
    )
    parser.add_argument(
        "--no-remove-stale",
        action="store_true",
        help="Do not delete registry entries missing from --dir",
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Clear all existing vectors and ingestion registry before ingesting",
    )
    parser.add_argument(
        "--wipe-chat",
        action="store_true",
        help="Also clear chat_messages when using --wipe",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize database schema before ingesting",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print ingestion status and exit",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    _configure_backend(args)
    status_only = args.status and not any(
        [args.file, args.url, args.urls, args.wipe, args.init]
    )
    if status_only:
        from src.db.status import print_ingestion_status

        print_ingestion_status()
        return 0

    if args.low_memory:
        os.environ["INGEST_USE_SEMANTIC_CHUNKING"] = "false"
        os.environ["INGEST_CLEAR_BM25_EACH_FILE"] = "false"
        print("Low-memory mode: sentence chunking for PDFs, deferred BM25 cache clear")

    # Load embeddings BEFORE pipeline/vector-store imports (Windows ONNX DLL order).
    from src.config import configure_for_ingest

    configure_for_ingest()

    if args.init or args.wipe:
        from src.db.init import init_database

        init_database()

    if args.wipe:
        from src.db.reset import wipe_ingestion_data

        cleared = wipe_ingestion_data(include_chat=args.wipe_chat)
        print("Wiped existing ingestion data:")
        for table, count in cleared.items():
            if table == "backend":
                print(f"  backend: {count}")
            else:
                print(f"  {table}: cleared")

    ran_ingest = False
    if args.file:
        ingest_single_file(args.file, force=args.full)
        ran_ingest = True
    elif args.url:
        ingest_single_url(args.url, force=args.full)
        ran_ingest = True
    elif args.urls:
        ingest_url_list(args.urls, force=args.full)
        ran_ingest = True
    elif args.wipe or not args.init:
        ingest_from_directory(
            args.dir,
            incremental=not args.full,
            remove_stale=not args.no_remove_stale,
        )
        ran_ingest = True

    if ran_ingest or args.status:
        from src.db.status import print_ingestion_status

        print()
        print_ingestion_status()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())