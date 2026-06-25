"""Ingestion package. Import from submodules directly to avoid heavy startup imports."""

__all__ = [
    "IngestionPipeline",
    "ingest_directory",
    "ingest_file",
    "ingest_url",
]


def __getattr__(name: str):
    if name in __all__:
        from src.ingestion import pipeline

        return getattr(pipeline, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")