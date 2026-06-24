import json
from dataclasses import dataclass
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from src.ingestion.loaders import SourceRecord
from src.db.vector_config import get_db_params

REGISTRY_TABLE = "ingestion_registry"


@dataclass
class RegistryEntry:
    source_id: str
    source_path: str
    source_type: str
    content_hash: str
    ref_doc_id: str
    file_mtime: float | None
    chunk_count: int
    metadata: dict[str, Any]


class DocumentRegistry:
    def __init__(self) -> None:
        self._ensure_table()

    def _connect(self):
        return psycopg2.connect(**get_db_params())

    def _ensure_table(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {REGISTRY_TABLE} (
                        source_id VARCHAR(64) PRIMARY KEY,
                        source_path TEXT NOT NULL,
                        source_type VARCHAR(20) NOT NULL,
                        content_hash VARCHAR(64) NOT NULL,
                        ref_doc_id VARCHAR(64) NOT NULL,
                        file_mtime DOUBLE PRECISION,
                        chunk_count INTEGER DEFAULT 0,
                        metadata JSONB DEFAULT '{{}}'::jsonb,
                        indexed_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )
            conn.commit()

    def get(self, source_id: str) -> RegistryEntry | None:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM {REGISTRY_TABLE} WHERE source_id = %s",
                    (source_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return RegistryEntry(
            source_id=row["source_id"],
            source_path=row["source_path"],
            source_type=row["source_type"],
            content_hash=row["content_hash"],
            ref_doc_id=row["ref_doc_id"],
            file_mtime=row["file_mtime"],
            chunk_count=row["chunk_count"] or 0,
            metadata=row["metadata"] or {},
        )

    def list_all(self) -> list[RegistryEntry]:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SELECT * FROM {REGISTRY_TABLE}")
                rows = cur.fetchall()
        return [
            RegistryEntry(
                source_id=row["source_id"],
                source_path=row["source_path"],
                source_type=row["source_type"],
                content_hash=row["content_hash"],
                ref_doc_id=row["ref_doc_id"],
                file_mtime=row["file_mtime"],
                chunk_count=row["chunk_count"] or 0,
                metadata=row["metadata"] or {},
            )
            for row in rows
        ]

    def is_unchanged(self, source: SourceRecord) -> bool:
        entry = self.get(source.source_id)
        if not entry:
            return False
        if entry.content_hash != source.content_hash:
            return False
        if source.file_mtime is not None and entry.file_mtime != source.file_mtime:
            return False
        return True

    def upsert(
        self,
        source: SourceRecord,
        *,
        ref_doc_id: str,
        chunk_count: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {REGISTRY_TABLE} (
                        source_id, source_path, source_type, content_hash,
                        ref_doc_id, file_mtime, chunk_count, metadata, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (source_id) DO UPDATE SET
                        source_path = EXCLUDED.source_path,
                        source_type = EXCLUDED.source_type,
                        content_hash = EXCLUDED.content_hash,
                        ref_doc_id = EXCLUDED.ref_doc_id,
                        file_mtime = EXCLUDED.file_mtime,
                        chunk_count = EXCLUDED.chunk_count,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    (
                        source.source_id,
                        source.source_path,
                        source.source_type,
                        source.content_hash,
                        ref_doc_id,
                        source.file_mtime,
                        chunk_count,
                        json.dumps(metadata or {}),
                    ),
                )
            conn.commit()

    def delete(self, source_id: str) -> str | None:
        entry = self.get(source_id)
        if not entry:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {REGISTRY_TABLE} WHERE source_id = %s",
                    (source_id,),
                )
            conn.commit()
        return entry.ref_doc_id

    def find_stale_source_ids(self, active_sources: list[SourceRecord]) -> list[str]:
        active_ids = {source.source_id for source in active_sources}
        return [
            entry.source_id
            for entry in self.list_all()
            if entry.source_id not in active_ids and entry.source_type != "web"
        ]