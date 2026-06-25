import os

from llama_index.core import Settings
from llama_index.core.node_parser import (
    MarkdownNodeParser,
    SemanticSplitterNodeParser,
    SentenceSplitter,
)
from llama_index.core.schema import BaseNode, Document
from llama_index.core.node_parser import NodeParser

from src.ingestion.loaders import sanitize_text
from src.ingestion.metadata import COURSE_METADATA_KEYS, stable_hash


def use_semantic_chunking() -> bool:
    return os.getenv("INGEST_USE_SEMANTIC_CHUNKING", "false").lower() == "true"


def get_sentence_splitter() -> SentenceSplitter:
    return SentenceSplitter(
        chunk_size=Settings.chunk_size,
        chunk_overlap=Settings.chunk_overlap,
    )


def get_semantic_splitter() -> SemanticSplitterNodeParser:
    return SemanticSplitterNodeParser(
        buffer_size=1,
        breakpoint_percentile_threshold=95,
        embed_model=Settings.embed_model,
    )


def get_parser_for_source_type(source_type: str) -> NodeParser:
    sentence_splitter = get_sentence_splitter()
    if source_type == "markdown":
        return MarkdownNodeParser()
    if source_type in {"pdf", "web"} and use_semantic_chunking():
        return get_semantic_splitter()
    return sentence_splitter


def _attach_chunk_metadata(nodes: list[BaseNode], source_type: str) -> list[BaseNode]:
    sentence_splitter = get_sentence_splitter()
    refined: list[BaseNode] = []

    for node in nodes:
        if len(node.get_content()) > Settings.chunk_size * 1.5:
            refined.extend(sentence_splitter.get_nodes_from_documents([Document(text=node.get_content(), metadata=node.metadata)]))
        else:
            refined.append(node)

    for index, node in enumerate(refined):
        clean_text = sanitize_text(node.get_content())
        node.text = clean_text
        metadata = dict(node.metadata or {})
        metadata["chunk_index"] = index
        metadata["chunk_hash"] = stable_hash(clean_text)
        uses_semantic = source_type in {"pdf", "web"} and use_semantic_chunking()
        metadata["chunking_strategy"] = (
            "markdown_headers+sentence"
            if source_type == "markdown"
            else "semantic+sentence"
            if uses_semantic
            else "sentence"
            if source_type in {"pdf", "web"}
            else "sentence"
        )
        node.metadata = metadata
    return refined


def _course_metadata_from_document(document: Document) -> dict:
    metadata = document.metadata or {}
    course_meta = {key: metadata[key] for key in COURSE_METADATA_KEYS if metadata.get(key)}
    extra_ids = metadata.get("course_ids")
    if extra_ids:
        course_meta["course_ids"] = extra_ids
    return course_meta


def _apply_course_metadata(nodes: list[BaseNode], course_meta: dict) -> list[BaseNode]:
    if not course_meta:
        return nodes
    for node in nodes:
        node.metadata = {**course_meta, **(node.metadata or {})}
        for key, value in course_meta.items():
            node.metadata[key] = value
    return nodes


def chunk_documents(documents: list[Document]) -> list[BaseNode]:
    all_nodes: list[BaseNode] = []
    for document in documents:
        source_type = (document.metadata or {}).get("source_type", "text")
        course_meta = _course_metadata_from_document(document)
        parser = get_parser_for_source_type(source_type)
        nodes = parser.get_nodes_from_documents([document])
        nodes = _attach_chunk_metadata(nodes, source_type)
        all_nodes.extend(_apply_course_metadata(nodes, course_meta))
    return all_nodes