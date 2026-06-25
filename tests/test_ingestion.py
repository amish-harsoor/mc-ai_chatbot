import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.chunkers import chunk_documents
from src.ingestion.loaders import (
    discover_local_sources,
    get_skip_filenames,
    load_markdown,
    load_text,
    should_skip_file,
)
from src.ingestion.metadata import (
    build_course_metadata,
    enrich_document_metadata,
    extract_course_ids,
    extract_course_title,
    extract_primary_course_id,
    merge_course_metadata,
    parse_markdown_frontmatter,
    source_id_for_path,
    stable_hash,
)
from src.ingestion.pipeline import IngestionPipeline
from src.ingestion.registry import DocumentRegistry
from src.ingestion.loaders import SourceRecord


@pytest.fixture
def sample_markdown_file(tmp_path):
    path = tmp_path / "4606.md"
    path.write_text(
        """---
title: Budget Analysis
course_id: "4606"
department: Finance
---

# Budget Analysis

Course **4606** covers federal budget analysis.

## Learning Objectives

- Understand appropriations
- Analyze budget documents
""",
        encoding="utf-8",
    )
    return path


def test_parse_markdown_frontmatter():
    text = "---\ntitle: Test\ncourse_id: '1234'\n---\n\n# Heading\nBody"
    metadata, body = parse_markdown_frontmatter(text)
    assert metadata["title"] == "Test"
    assert metadata["course_id"] == "1234"
    assert "# Heading" in body


def test_extract_course_ids_ignores_phone_numbers_and_years():
    text = (
        "888.545.8574 | © 2025 Management Concepts\n"
        "Course Number: 4606\n"
        "https://www.managementconcepts.com/course/id/4606"
    )
    assert extract_course_ids(text, source_path="4606.pdf") == ["4606"]


def test_extract_primary_course_id_prefers_explicit_course_number():
    text = "888.545.8574 | Course Number: 4606 | Microsoft Office 2010"
    assert extract_primary_course_id(text, source_path="notes.pdf") == "4606"


def test_extract_course_title_from_pdf_header():
    text = (
        "888.545.8574 | ManagementConcepts.com | © 2025 Management Concepts\n\n"
        "Introduction to Data Visualization\n"
        "Course Number: 4606\n"
        "Length: 2 Days"
    )
    assert extract_course_title(text) == "Introduction to Data Visualization"


def test_build_course_metadata_extracts_structured_fields():
    text = (
        "Introduction to Data Visualization\n"
        "Course Number: 4606\n"
        "Length: 2 Days\n"
        "Primary Delivery Method: Instructor-led online"
    )
    metadata = build_course_metadata(text=text, source_path="4606.pdf")
    assert metadata["course_id"] == "4606"
    assert metadata["course_title"] == "Introduction to Data Visualization"
    assert metadata["duration"] == "2 Days"
    assert "Instructor-led online" in metadata["delivery_method"]


def test_merge_course_metadata_prefers_first_non_empty_value():
    first = {"course_id": "4606", "duration": "2 Days"}
    second = {"course_id": "9999", "course_title": "Intro"}
    merged = merge_course_metadata(first, second)
    assert merged["course_id"] == "4606"
    assert merged["course_title"] == "Intro"


def test_enrich_document_metadata_includes_course_and_section():
    metadata = enrich_document_metadata(
        text="# Federal Budget\nCourse Number: 4606",
        source_type="markdown",
        source_path="/tmp/4606.md",
        base_metadata={"department": "Finance", "title": "Federal Budget"},
    )
    assert metadata["course_id"] == "4606"
    assert metadata["course_title"] == "Federal Budget"
    assert metadata["department"] == "Finance"
    assert metadata["section_title"] == "Federal Budget"
    assert metadata["source_type"] == "markdown"


def test_source_id_is_stable_for_same_path():
    first = source_id_for_path("data/course.md")
    second = source_id_for_path("data/course.md")
    assert first == second
    assert len(first) == 64


def test_should_skip_problem_pdf():
    get_skip_filenames.cache_clear()
    assert should_skip_file("1.2.1.3.1_Mod-6-2.pdf") is True
    assert should_skip_file("4606.pdf") is False


def test_discover_local_sources_excludes_skipped_files(tmp_path):
    get_skip_filenames.cache_clear()
    (tmp_path / "4606.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "1.2.1.3.1_Mod-6-2.pdf").write_bytes(b"%PDF-1.4")

    sources = discover_local_sources(tmp_path)
    assert len(sources) == 1
    assert sources[0].source_path.endswith("4606.pdf")


def test_discover_local_sources_finds_supported_files(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "b.md").write_text("# Title", encoding="utf-8")
    (tmp_path / "ignore.docx").write_bytes(b"doc")

    sources = discover_local_sources(tmp_path)
    assert len(sources) == 2
    assert {source.source_type for source in sources} == {"pdf", "markdown"}


def test_load_markdown_extracts_frontmatter(sample_markdown_file):
    docs = load_markdown(sample_markdown_file)
    assert len(docs) == 1
    assert docs[0].metadata["title"] == "Budget Analysis"
    assert docs[0].metadata["course_title"] == "Budget Analysis"
    assert docs[0].metadata["course_id"] == "4606"
    assert "Learning Objectives" in docs[0].text


def test_load_pdf_propagates_course_metadata_to_all_pages():
    from src.ingestion.loaders import load_pdf

    pdf_path = Path(__file__).resolve().parents[1] / "src" / "data" / "4606.pdf"
    if not pdf_path.exists():
        pytest.skip("Sample PDF not available")

    docs = load_pdf(pdf_path)
    assert len(docs) > 1
    for doc in docs:
        assert doc.metadata["course_id"] == "4606"
        assert doc.metadata["course_title"] == "Introduction to Data Visualization"
        assert doc.metadata["duration"] == "2 Days"


def test_chunk_documents_adds_chunk_metadata(sample_markdown_file):
    docs = load_markdown(sample_markdown_file)
    nodes = chunk_documents(docs)
    assert nodes
    assert all("chunk_hash" in node.metadata for node in nodes)
    assert all("chunk_index" in node.metadata for node in nodes)
    assert nodes[0].metadata["chunking_strategy"] == "markdown_headers+sentence"


def test_registry_is_unchanged_detects_same_hash():
    registry = DocumentRegistry.__new__(DocumentRegistry)
    registry.get = MagicMock(
        return_value=type(
            "Entry",
            (),
            {
                "content_hash": "abc",
                "file_mtime": 1.0,
            },
        )()
    )

    source = SourceRecord(
        source_id="id",
        source_path="/tmp/a.md",
        source_type="markdown",
        content_hash="abc",
        file_mtime=1.0,
    )
    assert registry.is_unchanged(source) is True


def test_pipeline_skips_unchanged_source():
    mock_registry = MagicMock()
    mock_registry.is_unchanged.return_value = True
    mock_index = MagicMock()

    pipeline = IngestionPipeline(index=mock_index, registry=mock_registry)
    source = SourceRecord(
        source_id="id",
        source_path="/tmp/a.md",
        source_type="markdown",
        content_hash=stable_hash("same"),
        file_mtime=1.0,
    )

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write("# Same\ncontent")
        path = handle.name

    try:
        docs = load_text(path)
        result = pipeline.ingest_documents(docs, source)
    finally:
        Path(path).unlink(missing_ok=True)

    assert result.action == "skipped"
    mock_index.insert_nodes.assert_not_called()


def test_pipeline_deduplicates_identical_chunks():
    mock_registry = MagicMock()
    mock_registry.is_unchanged.return_value = False
    mock_registry.get.return_value = None
    mock_index = MagicMock()

    pipeline = IngestionPipeline(index=mock_index, registry=mock_registry)
    duplicate_text = "Identical chunk " * 20
    source = SourceRecord(
        source_id="id",
        source_path="/tmp/a.txt",
        source_type="text",
        content_hash=stable_hash(duplicate_text),
        file_mtime=1.0,
    )

    from llama_index.core import Document

    docs = [
        Document(
            text=duplicate_text,
            metadata={"source_type": "text", "source_path": "/tmp/a.txt"},
            id_="doc-1",
        )
    ]

    with patch("src.ingestion.pipeline.chunk_documents") as mock_chunk:
        from llama_index.core.schema import TextNode

        node = TextNode(text=duplicate_text, metadata={"chunk_hash": stable_hash(duplicate_text)})
        mock_chunk.return_value = [node, node]

        result = pipeline.ingest_documents(docs, source)

    assert result.chunk_count == 1
    assert result.skipped_duplicate_chunks == 1
    mock_index.insert_nodes.assert_called_once()