"""Lightweight retrieval cache reset — safe to import during ingestion (no BM25/torch)."""

import sys


def clear_retrieval_caches() -> None:
    """Clear in-process retrieval caches if the retrieval module was already loaded."""
    retrieval = sys.modules.get("src.chatbot.retrieval")
    if retrieval is None:
        return

    retrieval._bm25_nodes_cache = None
    retrieval._base_hybrid_retriever = None
    retrieval._node_postprocessors_rerank = None
    retrieval._node_postprocessors_no_rerank = None
    if hasattr(retrieval, "_node_postprocessors"):
        retrieval._node_postprocessors = None
    reranker_factory = getattr(retrieval, "_create_reranker", None)
    if reranker_factory is not None and hasattr(reranker_factory, "cache_clear"):
        try:
            reranker_factory.cache_clear()
        except Exception:
            pass