from llama_index.core import Settings
from llama_index.core.node_parser import (
    MarkdownNodeParser,
    SemanticSplitterNodeParser,
    SentenceSplitter,
)
from llama_index.core.schema import BaseNode, Document
from llama_index.core.node_parser import NodeParser

from src.ingestion.metadata import stable_hash


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
    if source_type in {"pdf", "web"}:
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
        metadata = dict(node.metadata or {})
        metadata["chunk_index"] = index
        metadata["chunk_hash"] = stable_hash(node.get_content())
        metadata["chunking_strategy"] = (
            "markdown_headers+sentence"
            if source_type == "markdown"
            else "semantic+sentence"
            if source_type in {"pdf", "web"}
            else "sentence"
        )
        node.metadata = metadata
    return refined


def chunk_documents(documents: list[Document]) -> list[BaseNode]:
    all_nodes: list[BaseNode] = []
    for document in documents:
        source_type = (document.metadata or {}).get("source_type", "text")
        parser = get_parser_for_source_type(source_type)
        nodes = parser.get_nodes_from_documents([document])
        all_nodes.extend(_attach_chunk_metadata(nodes, source_type))
    return all_nodes