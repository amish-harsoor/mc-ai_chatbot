import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from llama_index.core import Document
from llama_index.readers.file import MarkdownReader, PDFReader

from src.ingestion.metadata import (
    enrich_document_metadata,
    file_content_hash,
    parse_markdown_frontmatter,
    source_id_for_path,
    source_id_for_url,
)

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}
WEB_USER_AGENT = "mc-ai-chatbot-ingestion/1.0"


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


def load_pdf(path: str | Path) -> list[Document]:
    path = Path(path)
    reader = PDFReader(return_full_document=False)
    pages = reader.load_data(file=path)
    documents: list[Document] = []
    for page in pages:
        metadata = enrich_document_metadata(
            text=page.text,
            source_type="pdf",
            source_path=str(path.resolve()),
            base_metadata=dict(page.metadata or {}),
            page_label=page.metadata.get("page_label") if page.metadata else None,
        )
        documents.append(
            Document(
                text=page.text,
                metadata=metadata,
                id_=source_id_for_path(path),
            )
        )
    return documents


def load_markdown(path: str | Path) -> list[Document]:
    path = Path(path)
    raw_text = path.read_text(encoding="utf-8")
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
    return [
        Document(
            text=text,
            metadata=metadata,
            id_=source_id_for_path(path),
        )
    ]


def load_text(path: str | Path) -> list[Document]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    metadata = enrich_document_metadata(
        text=text,
        source_type="text",
        source_path=str(path.resolve()),
    )
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
    text = main.get_text("\n", strip=True) if main else soup.get_text("\n", strip=True)

    metadata = enrich_document_metadata(
        text=text,
        source_type="web",
        source_path=url,
        base_metadata={"url": url, "title": title},
        section_title=title,
    )
    return [
        Document(
            text=text,
            metadata=metadata,
            id_=source_id_for_url(url),
        )
    ]

