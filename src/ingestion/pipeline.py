import logging
from dataclasses import dataclass, field
from pathlib import Path

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import Document

from src.ingestion.chunkers import chunk_documents
from src.ingestion.loaders import (
    SourceRecord,
    discover_local_sources,
    load_local_file,
    load_web,
)
from src.ingestion.metadata import (
    file_content_hash,
    source_id_for_path,
    source_id_for_url,
    stable_hash,
)
from src.ingestion.registry import DocumentRegistry
from src.ingestion.vector_store import load_index

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    source_path: str
    action: str
    chunk_count: int = 0
    skipped_duplicate_chunks: int = 0
    message: str = ""


@dataclass
class PipelineSummary:
    indexed: list[IngestionResult] = field(default_factory=list)
    skipped: list[IngestionResult] = field(default_factory=list)
    deleted: list[IngestionResult] = field(default_factory=list)
    failed: list[IngestionResult] = field(default_factory=list)

    @property
    def total_chunks(self) -> int:
        return sum(item.chunk_count for item in self.indexed)


class IngestionPipeline:
    def __init__(
        self,
        index: VectorStoreIndex | None = None,
        registry: DocumentRegistry | None = None,
    ) -> None:
        self.index = index or load_index()
        self.registry = registry or DocumentRegistry()
        self._known_chunk_hashes: set[str] = set()

    def _dedupe_nodes(self, nodes: list) -> tuple[list, int]:
        unique_nodes = []
        skipped = 0
        for node in nodes:
            chunk_hash = (node.metadata or {}).get("chunk_hash")
            if chunk_hash and chunk_hash in self._known_chunk_hashes:
                skipped += 1
                continue
            if chunk_hash:
                self._known_chunk_hashes.add(chunk_hash)
            unique_nodes.append(node)
        return unique_nodes, skipped

    def _remove_source(self, source_id: str, source_path: str) -> IngestionResult | None:
        ref_doc_id = self.registry.delete(source_id)
        if not ref_doc_id:
            return None
        try:
            self.index.delete_ref_doc(ref_doc_id, delete_from_docstore=True)
        except Exception as exc:
            logger.warning("Failed to delete ref_doc_id %s: %s", ref_doc_id, exc)
        return IngestionResult(
            source_path=source_path,
            action="deleted",
            message="Removed stale vectors for deleted or moved source",
        )

    def ingest_documents(
        self,
        documents: list[Document],
        source: SourceRecord,
        *,
        force: bool = False,
    ) -> IngestionResult:
        if not force and self.registry.is_unchanged(source):
            return IngestionResult(
                source_path=source.source_path,
                action="skipped",
                message="Source unchanged since last ingest",
            )

        existing = self.registry.get(source.source_id)
        if existing:
            try:
                self.index.delete_ref_doc(existing.ref_doc_id, delete_from_docstore=True)
            except Exception as exc:
                logger.warning(
                    "Failed to delete previous vectors for %s: %s",
                    source.source_path,
                    exc,
                )

        nodes = chunk_documents(documents)
        unique_nodes, skipped_chunks = self._dedupe_nodes(nodes)
        if not unique_nodes:
            return IngestionResult(
                source_path=source.source_path,
                action="skipped",
                message="No unique chunks produced",
            )

        self.index.insert_nodes(unique_nodes)
        ref_doc_id = documents[0].id_ or source.source_id
        metadata = dict(documents[0].metadata or {})
        self.registry.upsert(
            source,
            ref_doc_id=ref_doc_id,
            chunk_count=len(unique_nodes),
            metadata=metadata,
        )

        return IngestionResult(
            source_path=source.source_path,
            action="indexed",
            chunk_count=len(unique_nodes),
            skipped_duplicate_chunks=skipped_chunks,
            message="Indexed with semantic chunking and metadata",
        )

    def ingest_file(self, path: str | Path, *, force: bool = False) -> IngestionResult:
        path = Path(path)
        source_type = path.suffix.lower()
        if source_type == ".pdf":
            stype = "pdf"
        elif source_type in {".md", ".markdown"}:
            stype = "markdown"
        else:
            stype = "text"

        source = SourceRecord(
            source_id=source_id_for_path(path),
            source_path=str(path.resolve()),
            source_type=stype,
            content_hash=file_content_hash(path),
            file_mtime=path.stat().st_mtime,
        )
        documents = load_local_file(path)
        return self.ingest_documents(documents, source, force=force)

    def ingest_url(self, url: str, *, force: bool = False) -> IngestionResult:
        documents = load_web(url)
        content = documents[0].text if documents else ""
        source = SourceRecord(
            source_id=source_id_for_url(url),
            source_path=url,
            source_type="web",
            content_hash=stable_hash(content),
            file_mtime=None,
        )
        return self.ingest_documents(documents, source, force=force)

    def sync_directory(
        self,
        data_dir: str | Path = "data",
        *,
        incremental: bool = True,
        remove_stale: bool = True,
    ) -> PipelineSummary:
        summary = PipelineSummary()
        sources = discover_local_sources(data_dir)
        if not sources:
            logger.warning("No supported documents found in %s", data_dir)
            return summary

        if remove_stale:
            for source_id in self.registry.find_stale_source_ids(sources):
                entry = self.registry.get(source_id)
                if not entry:
                    continue
                deleted = self._remove_source(source_id, entry.source_path)
                if deleted:
                    summary.deleted.append(deleted)

        for source in sources:
            try:
                if incremental and self.registry.is_unchanged(source):
                    summary.skipped.append(
                        IngestionResult(
                            source_path=source.source_path,
                            action="skipped",
                            message="Unchanged source",
                        )
                    )
                    continue

                documents = load_local_file(source.source_path)
                result = self.ingest_documents(
                    documents,
                    source,
                    force=not incremental,
                )
                if result.action == "indexed":
                    summary.indexed.append(result)
                else:
                    summary.skipped.append(result)
            except Exception as exc:
                logger.error("Failed to ingest %s: %s", source.source_path, exc)
                summary.failed.append(
                    IngestionResult(
                        source_path=source.source_path,
                        action="failed",
                        message=str(exc),
                    )
                )
        return summary


def ingest_directory(
    data_dir: str | Path = "data",
    *,
    incremental: bool = True,
    remove_stale: bool = True,
) -> PipelineSummary:
    return IngestionPipeline().sync_directory(
        data_dir,
        incremental=incremental,
        remove_stale=remove_stale,
    )


def ingest_file(path: str | Path, *, force: bool = False) -> IngestionResult:
    return IngestionPipeline().ingest_file(path, force=force)


def ingest_url(url: str, *, force: bool = False) -> IngestionResult:
    return IngestionPipeline().ingest_url(url, force=force)