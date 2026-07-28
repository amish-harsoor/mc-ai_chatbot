import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from llama_index.core import Document
from llama_index.readers.file import MarkdownReader, PDFReader

from src.ingestion.metadata import (
    enrich_document_metadata,
    file_content_hash,
    merge_course_metadata,
    parse_markdown_frontmatter,
    source_id_for_path,
    source_id_for_url,
)
from src.ingestion.pricing import apply_catalog_prices, is_gsa_price_list

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}
WEB_USER_AGENT = "mc-ai-chatbot-ingestion/1.0"

DEFAULT_SKIP_FILENAMES = {
    "1.2.1.3.1_mod-6-2.pdf",
}


def sanitize_text(text: str | None) -> str:
    """Remove NUL bytes that break Postgres text inserts."""
    if not text:
        return ""
    return text.replace("\x00", "")


@lru_cache(maxsize=1)
def get_skip_filenames() -> frozenset[str]:
    """Basenames to exclude from directory ingestion (lowercased)."""
    names = set(DEFAULT_SKIP_FILENAMES)
    for path in (
        Path("ingest_skip.txt"),
        Path(__file__).resolve().parents[2] / "ingest_skip.txt",
    ):
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                value = line.strip()
                if value and not value.startswith("#"):
                    names.add(value.lower())
    env_value = os.getenv("INGEST_SKIP_FILES", "")
    for part in env_value.split(","):
        value = part.strip()
        if value:
            names.add(value.lower())
    return frozenset(names)


def should_skip_file(path: str | Path) -> bool:
    return Path(path).name.lower() in get_skip_filenames()


@dataclass
class SourceRecord:
    source_id: str
    source_path: str
    source_type: str
    content_hash: str
    file_mtime: float | None = None


def _file_mtime(path: Path) -> float:
    return path.stat().st_mtime


def _content_hash_for_file(path: Path) -> str:
    return file_content_hash(path)


def discover_local_sources(data_dir: str | Path) -> list[SourceRecord]:
    root = Path(data_dir)
    if not root.exists():
        return []

    records: list[SourceRecord] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if should_skip_file(path):
            logger.info("Skipping excluded file: %s", path)
            continue
        source_type = _extension_to_source_type(path.suffix)
        records.append(
            SourceRecord(
                source_id=source_id_for_path(path),
                source_path=str(path.resolve()),
                source_type=source_type,
                content_hash=_content_hash_for_file(path),
                file_mtime=_file_mtime(path),
            )
        )
    return records


def _extension_to_source_type(suffix: str) -> str:
    suffix = suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    return "text"


def _propagate_course_metadata(documents: list[Document]) -> None:
    """Copy canonical course fields from the richest page onto every page of the same file."""
    canonical = merge_course_metadata(*(doc.metadata for doc in documents))
    if not canonical:
        return
    canonical = apply_catalog_prices(canonical)
    for document in documents:
        for key, value in canonical.items():
            document.metadata[key] = value


def load_pdf(path: str | Path) -> list[Document]:
    path = Path(path)
    reader = PDFReader(return_full_document=False)
    pages = reader.load_data(file=path)
    documents: list[Document] = []
    for page in pages:
        page_text = sanitize_text(page.text)
        metadata = enrich_document_metadata(
            text=page_text,
            source_type="pdf",
            source_path=str(path.resolve()),
            base_metadata=dict(page.metadata or {}),
            page_label=page.metadata.get("page_label") if page.metadata else None,
        )
        documents.append(
            Document(
                text=page_text,
                metadata=metadata,
                id_=source_id_for_path(path),
            )
        )
    full_text = "\n".join(doc.text for doc in documents)
    if is_gsa_price_list(path, full_text):
        # GSA bulk lists are not the official price source — strip any parsed price.
        for document in documents:
            document.metadata.pop("price", None)
    else:
        _propagate_course_metadata(documents)
    return documents


def load_markdown(path: str | Path) -> list[Document]:
    path = Path(path)
    raw_text = sanitize_text(path.read_text(encoding="utf-8"))
    frontmatter_meta, body = parse_markdown_frontmatter(raw_text)

    if body.strip():
        text = body
    else:
        reader = MarkdownReader()
        text = "\n\n".join(doc.text for doc in reader.load_data(file=path))

    metadata = enrich_document_metadata(
        text=text,
        source_type="markdown",
        source_path=str(path.resolve()),
        base_metadata=frontmatter_meta,
    )
    metadata = apply_catalog_prices(metadata)
    return [
        Document(
            text=text,
            metadata=metadata,
            id_=source_id_for_path(path),
        )
    ]


def load_text(path: str | Path) -> list[Document]:
    path = Path(path)
    text = sanitize_text(path.read_text(encoding="utf-8"))
    metadata = enrich_document_metadata(
        text=text,
        source_type="text",
        source_path=str(path.resolve()),
    )
    metadata = apply_catalog_prices(metadata)
    return [
        Document(
            text=text,
            metadata=metadata,
            id_=source_id_for_path(path),
        )
    ]


def load_local_file(path: str | Path) -> list[Document]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return load_pdf(path)
    if suffix in {".md", ".markdown"}:
        return load_markdown(path)
    if suffix == ".txt":
        return load_text(path)
    raise ValueError(f"Unsupported file type: {suffix}")


def load_web(url: str, timeout: int = 20) -> list[Document]:
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": WEB_USER_AGENT},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else urlparse(url).path
    main = soup.find("main") or soup.find("article") or soup.body
    text = sanitize_text(main.get_text("\n", strip=True) if main else soup.get_text("\n", strip=True))

    metadata = enrich_document_metadata(
        text=text,
        source_type="web",
        source_path=url,
        base_metadata={"url": url, "title": title},
        section_title=title,
    )
    metadata = apply_catalog_prices(metadata)
    return [
        Document(
            text=text,
            metadata=metadata,
            id_=source_id_for_url(url),
        )
    ]

