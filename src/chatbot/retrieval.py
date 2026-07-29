import logging
import os
from functools import lru_cache
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core.postprocessor import LongContextReorder, SentenceTransformerRerank
from llama_index.core.postprocessor.optimizer import SentenceEmbeddingOptimizer
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.retrievers import QueryFusionRetriever, VectorIndexRetriever
from llama_index.core.retrievers.fusion_retriever import FUSION_MODES
from llama_index.core.schema import BaseNode, NodeWithScore, QueryBundle, TextNode
from llama_index.core.vector_stores import FilterCondition, FilterOperator
from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters
from src.chatbot.query_context import UserProfile, build_query_expansion_terms
from src.db.vector_config import get_db_params, get_vector_table_name

logger = logging.getLogger(__name__)

_bm25_nodes_cache: list | None = None
_base_hybrid_retriever: BaseRetriever | None = None
_node_postprocessors_rerank: list[BaseNodePostprocessor] | None = None
_node_postprocessors_no_rerank: list[BaseNodePostprocessor] | None = None


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


RETRIEVAL_VECTOR_TOP_K = _env_int("RETRIEVAL_VECTOR_TOP_K", 8)
RETRIEVAL_BM25_TOP_K = _env_int("RETRIEVAL_BM25_TOP_K", 8)
RETRIEVAL_FUSION_TOP_K = _env_int("RETRIEVAL_FUSION_TOP_K", 6)
RETRIEVAL_RERANK_TOP_N = _env_int("RETRIEVAL_RERANK_TOP_N", 4)
# Keep at 1: values >1 force an extra LLM call inside QueryFusionRetriever.
RETRIEVAL_NUM_QUERIES = _env_int("RETRIEVAL_NUM_QUERIES", 1)
RETRIEVAL_VECTOR_WEIGHT = _env_float("RETRIEVAL_VECTOR_WEIGHT", 0.6)
RETRIEVAL_BM25_WEIGHT = _env_float("RETRIEVAL_BM25_WEIGHT", 0.4)
CONTEXT_COMPRESSION_PERCENTILE = _env_float("CONTEXT_COMPRESSION_PERCENTILE", 0.0)
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
ENABLE_CONTEXT_COMPRESSION = os.getenv("ENABLE_CONTEXT_COMPRESSION", "false").lower() == "true"
ENABLE_RERANK = os.getenv("ENABLE_RERANK", "true").lower() in ("1", "true", "yes")

_course_title_catalog: dict[str, str] | None = None


def load_course_title_catalog(force: bool = False) -> dict[str, str]:
    """Display titles: official JSON catalog first, vector-store recovery as fallback."""
    global _course_title_catalog
    if _course_title_catalog is not None and not force:
        return _course_title_catalog

    from src.ingestion.course_catalog import load_course_catalog, title_map
    from src.ingestion.metadata import (
        extract_course_title,
        is_weak_course_title,
        prefer_course_title,
    )

    # Official MC catalog is authoritative for titles
    load_course_catalog(force=force)
    catalog: dict[str, str] = dict(title_map())

    # Fill any missing IDs from vector store / multi-line PDF recovery
    table = get_vector_table_name()
    try:
        conn = psycopg2.connect(**get_db_params())
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT metadata_->>'course_id' AS course_id,
                           metadata_->>'course_title' AS course_title,
                           left(text, 800) AS text
                    FROM {table}
                    WHERE metadata_->>'course_id' IS NOT NULL
                    """
                )
                for row in cur.fetchall():
                    cid = str(row["course_id"] or "").strip()
                    if not cid or cid in catalog:
                        continue
                    stored = (row["course_title"] or "").strip() or None
                    recovered = extract_course_title(
                        row["text"] or "",
                        base_metadata={"course_title": stored},
                    )
                    best = prefer_course_title(recovered, stored)
                    if best and not is_weak_course_title(best):
                        catalog[cid] = best
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Course title catalog fallback load failed: %s", exc)

    _course_title_catalog = catalog
    if catalog:
        logger.info("Course title catalog ready (%s courses)", len(catalog))
    return catalog


class CourseMetadataPostprocessor(BaseNodePostprocessor):
    """Prepend official catalog fields (title, duration, level, price, delivery)."""

    def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> list[NodeWithScore]:
        from src.ingestion.course_catalog import apply_official_catalog, load_course_catalog
        from src.ingestion.pricing import apply_catalog_prices

        load_course_catalog()
        load_course_title_catalog()

        enriched: list[NodeWithScore] = []
        for node_with_score in nodes:
            metadata = dict(node_with_score.node.metadata or {})
            # Official JSON wins for title/duration/level/price/url
            metadata = apply_official_catalog(metadata)
            # Fill price from price DB/JSON if still missing
            metadata = apply_catalog_prices(metadata)

            source_text = node_with_score.node.get_content()

            header_parts: list[str] = []
            if metadata.get("course_id"):
                header_parts.append(f"Course ID: {metadata['course_id']}")
            if metadata.get("course_title"):
                header_parts.append(f"Title: {metadata['course_title']}")
            if metadata.get("duration"):
                header_parts.append(f"Duration: {metadata['duration']}")
            if metadata.get("level"):
                header_parts.append(f"Level: {metadata['level']}")
            if metadata.get("price"):
                header_parts.append(f"Cost: {metadata['price']}")
            if metadata.get("delivery_method"):
                header_parts.append(f"Delivery: {metadata['delivery_method']}")

            if not header_parts:
                enriched.append(node_with_score)
                continue

            prefix = " | ".join(header_parts)
            if source_text.startswith(prefix):
                # Still refresh metadata on the node for downstream use
                if hasattr(node_with_score.node, "metadata"):
                    node_with_score.node.metadata = metadata
                enriched.append(node_with_score)
                continue

            enriched_node = TextNode(
                id_=node_with_score.node.id_,
                text=f"{prefix}\n{source_text}",
                metadata=metadata,
            )
            enriched.append(
                NodeWithScore(node=enriched_node, score=node_with_score.score)
            )
        return enriched


class ProfileAwareRetriever(BaseRetriever):
    """Applies metadata filters with automatic fallback when results are empty."""

    def __init__(
        self,
        base_retriever: BaseRetriever,
        fallback_retriever: BaseRetriever | None = None,
    ) -> None:
        super().__init__()
        self._base_retriever = base_retriever
        self._fallback_retriever = fallback_retriever or base_retriever

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        nodes = self._base_retriever.retrieve(query_bundle)
        if nodes:
            return nodes
        if self._fallback_retriever is not self._base_retriever:
            logger.debug("Metadata-filtered retrieval returned no results; retrying without filters")
            return self._fallback_retriever.retrieve(query_bundle)
        return nodes


def _node_matches_filter(node: BaseNode, metadata_filter: MetadataFilter) -> bool:
    metadata = node.metadata or {}
    value = metadata.get(metadata_filter.key)
    if value is None:
        return False
    if metadata_filter.operator == FilterOperator.EQ:
        return str(value) == str(metadata_filter.value)
    return False


def _node_matches_filters(node: BaseNode, metadata_filters: MetadataFilters) -> bool:
    if not metadata_filters.filters:
        return True
    if metadata_filters.condition == FilterCondition.OR:
        return any(_node_matches_filter(node, flt) for flt in metadata_filters.filters)
    return all(_node_matches_filter(node, flt) for flt in metadata_filters.filters)


class MetadataPostFilterRetriever(BaseRetriever):
    """Post-filter hybrid retrieval results by metadata without unfiltered fallback."""

    def __init__(
        self,
        base_retriever: BaseRetriever,
        metadata_filters: MetadataFilters,
    ) -> None:
        super().__init__()
        self._base_retriever = base_retriever
        self._metadata_filters = metadata_filters

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        nodes = self._base_retriever.retrieve(query_bundle)
        return [
            node_with_score
            for node_with_score in nodes
            if _node_matches_filters(node_with_score.node, self._metadata_filters)
        ]


class MergedRetriever(BaseRetriever):
    """Merge results from multiple retrievers, preserving first-seen order."""

    def __init__(self, retrievers: list[BaseRetriever]) -> None:
        super().__init__()
        self._retrievers = retrievers

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        merged: list[NodeWithScore] = []
        seen_ids: set[str] = set()
        for retriever in self._retrievers:
            for node_with_score in retriever.retrieve(query_bundle):
                node_id = node_with_score.node.id_
                if node_id in seen_ids:
                    continue
                seen_ids.add(node_id)
                merged.append(node_with_score)
        return merged


class QueryExpansionRetriever(BaseRetriever):
    """Prepends profile-aware query variants before delegating to the hybrid retriever."""

    def __init__(self, base_retriever: BaseRetriever, profile: UserProfile | None = None) -> None:
        super().__init__()
        self._base_retriever = base_retriever
        self._profile = profile or UserProfile()

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        query_str = query_bundle.query_str
        expanded_queries = build_query_expansion_terms(self._profile)
        if not expanded_queries:
            return self._base_retriever.retrieve(query_bundle)

        merged_query = "\n".join([query_str, *expanded_queries[:2]])
        return self._base_retriever.retrieve(QueryBundle(query_str=merged_query))


def _load_bm25_nodes(index: VectorStoreIndex) -> list:
    """Load all indexed nodes for BM25. PGVectorStore.get_nodes() requires filters/ids."""
    global _bm25_nodes_cache
    if _bm25_nodes_cache is not None:
        return _bm25_nodes_cache

    table = get_vector_table_name()
    try:
        conn = psycopg2.connect(**get_db_params())
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"SELECT node_id, text, metadata_ FROM {table} WHERE text IS NOT NULL"
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        nodes = [
            TextNode(
                id_=row["node_id"],
                text=row["text"] or "",
                metadata=row["metadata_"] or {},
            )
            for row in rows
        ]
        _bm25_nodes_cache = nodes
        logger.info("Loaded %s nodes for BM25 keyword retrieval from %s", len(nodes), table)
        return nodes
    except Exception as exc:
        logger.warning("Failed to load nodes for BM25 retrieval: %s", exc)
        return []


def clear_bm25_cache() -> None:
    global _bm25_nodes_cache, _base_hybrid_retriever
    global _node_postprocessors_rerank, _node_postprocessors_no_rerank, _course_title_catalog
    _bm25_nodes_cache = None
    _base_hybrid_retriever = None
    _node_postprocessors_rerank = None
    _node_postprocessors_no_rerank = None
    _course_title_catalog = None
    try:
        from src.ingestion.course_catalog import clear_course_catalog_cache

        clear_course_catalog_cache()
    except Exception:
        pass
    try:
        _create_reranker.cache_clear()
    except Exception:
        pass


def clear_retrieval_caches() -> None:
    """Release retrieval caches (BM25 nodes, fusion retriever, reranker)."""
    clear_bm25_cache()


def _get_bm25_retriever_class():
    try:
        from llama_index.retrievers.bm25 import BM25Retriever

        return BM25Retriever
    except ImportError as exc:
        logger.warning("BM25 retriever unavailable (package mismatch): %s", exc)
        return None


def create_vector_retriever(
    index: VectorStoreIndex,
    *,
    filters: MetadataFilters | None = None,
    similarity_top_k: int = RETRIEVAL_VECTOR_TOP_K,
) -> VectorIndexRetriever:
    return VectorIndexRetriever(
        index=index,
        similarity_top_k=similarity_top_k,
        filters=filters,
    )


def create_bm25_retriever(
    index: VectorStoreIndex,
    *,
    similarity_top_k: int = RETRIEVAL_BM25_TOP_K,
) -> BaseRetriever | None:
    BM25Retriever = _get_bm25_retriever_class()
    if BM25Retriever is None:
        return None
    nodes = _load_bm25_nodes(index)
    if not nodes:
        return None
    return BM25Retriever.from_defaults(
        nodes=nodes,
        similarity_top_k=similarity_top_k,
    )


def get_base_hybrid_retriever(index: VectorStoreIndex) -> BaseRetriever:
    """Return a cached vector+BM25 fusion retriever shared across chat sessions."""
    global _base_hybrid_retriever
    if _base_hybrid_retriever is not None:
        return _base_hybrid_retriever

    vector_retriever = create_vector_retriever(index, filters=None)
    bm25_retriever = create_bm25_retriever(index)

    if bm25_retriever is None:
        logger.warning("BM25 retriever unavailable; using vector retrieval only")
        _base_hybrid_retriever = vector_retriever
        return _base_hybrid_retriever

    _base_hybrid_retriever = QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        llm=Settings.llm,
        mode=FUSION_MODES.RECIPROCAL_RANK,
        similarity_top_k=RETRIEVAL_FUSION_TOP_K,
        num_queries=RETRIEVAL_NUM_QUERIES,
        retriever_weights=[RETRIEVAL_VECTOR_WEIGHT, RETRIEVAL_BM25_WEIGHT],
        use_async=False,
        verbose=False,
    )
    logger.info(
        "Hybrid retriever ready (vector=%s, bm25=%s, fusion_top_k=%s)",
        RETRIEVAL_VECTOR_TOP_K,
        RETRIEVAL_BM25_TOP_K,
        RETRIEVAL_FUSION_TOP_K,
    )
    return _base_hybrid_retriever


def initialize_retrieval(index: VectorStoreIndex) -> None:
    """Pre-warm BM25 index, fusion retriever, official catalog, and reranker."""
    from src.ingestion.course_catalog import load_course_catalog, sync_prices_to_price_catalog

    try:
        load_course_catalog(force=True)
        prices = sync_prices_to_price_catalog()
        if prices:
            logger.info("Official course price catalog ready (%s courses)", len(prices))
    except Exception as exc:
        logger.warning("Official course catalog initialization failed: %s", exc)

    try:
        load_course_title_catalog(force=True)
    except Exception as exc:
        logger.warning("Course title catalog initialization failed: %s", exc)

    get_base_hybrid_retriever(index)
    create_node_postprocessors()
    logger.info("Retrieval stack initialized")


def _has_course_id_filter(metadata_filters: MetadataFilters | None) -> bool:
    return bool(
        metadata_filters
        and any(flt.key == "course_id" for flt in metadata_filters.filters)
    )


def create_hybrid_retriever(
    index: VectorStoreIndex,
    *,
    metadata_filters: MetadataFilters | None = None,
    profile: UserProfile | None = None,
) -> BaseRetriever:
    # High-confidence course_id filter: vector-only (skip hybrid double-fetch + expansion noise).
    if metadata_filters and _has_course_id_filter(metadata_filters):
        return create_vector_retriever(index, filters=metadata_filters)

    base_hybrid = get_base_hybrid_retriever(index)

    if metadata_filters:
        vector_filtered = create_vector_retriever(index, filters=metadata_filters)
        inner = ProfileAwareRetriever(vector_filtered, base_hybrid)
    else:
        inner = base_hybrid

    return QueryExpansionRetriever(inner, profile=profile)


@lru_cache(maxsize=1)
def _create_reranker() -> SentenceTransformerRerank:
    return SentenceTransformerRerank(
        model=RERANK_MODEL,
        top_n=RETRIEVAL_RERANK_TOP_N,
    )


def create_node_postprocessors(
    *,
    skip_rerank: bool = False,
) -> list[BaseNodePostprocessor]:
    """Build postprocessors. Rerank is optional (ENABLE_RERANK=false or skip_rerank=True)."""
    global _node_postprocessors_rerank, _node_postprocessors_no_rerank

    use_rerank = ENABLE_RERANK and not skip_rerank
    cached = _node_postprocessors_rerank if use_rerank else _node_postprocessors_no_rerank
    if cached is not None:
        return cached

    processors: list[BaseNodePostprocessor] = []
    if use_rerank:
        processors.append(_create_reranker())
    if ENABLE_CONTEXT_COMPRESSION and CONTEXT_COMPRESSION_PERCENTILE > 0:
        processors.append(
            SentenceEmbeddingOptimizer(
                embed_model=Settings.embed_model,
                percentile_cutoff=CONTEXT_COMPRESSION_PERCENTILE,
            )
        )
    processors.extend(
        [
            LongContextReorder(),
            CourseMetadataPostprocessor(),
        ]
    )
    if use_rerank:
        _node_postprocessors_rerank = processors
    else:
        _node_postprocessors_no_rerank = processors
    return processors


def build_condense_prompt(profile: UserProfile) -> str:
    profile_hint = profile.summary() or "No structured profile captured yet."
    return f"""\
Given the following conversation between a user and an AI assistant, rewrite the user's last message into a standalone search query for a federal training course catalog.

User profile context: {profile_hint}

The rewritten query should:
- Preserve course IDs, departments, experience level, and career goals from the conversation
- Expand abbreviations into searchable terms (e.g. "budget" -> "federal budget analysis")
- Stay focused on course discovery and training recommendations
- Be concise but specific

Chat History:
{{chat_history}}

Standalone search query:"""