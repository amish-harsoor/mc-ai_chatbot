import logging
import os
from functools import lru_cache

import psycopg2
from psycopg2.extras import RealDictCursor
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core.postprocessor import LongContextReorder, SentenceTransformerRerank
from llama_index.core.postprocessor.optimizer import SentenceEmbeddingOptimizer
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.retrievers import QueryFusionRetriever, VectorIndexRetriever
from llama_index.core.retrievers.fusion_retriever import FUSION_MODES
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from llama_index.core.vector_stores.types import MetadataFilters
from llama_index.retrievers.bm25 import BM25Retriever

from src.chatbot.query_context import UserProfile, build_query_expansion_terms
from src.db.vector_config import get_db_params, get_vector_table_name

logger = logging.getLogger(__name__)

_bm25_nodes_cache: list | None = None
_base_hybrid_retriever: BaseRetriever | None = None
_node_postprocessors: list[BaseNodePostprocessor] | None = None


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


RETRIEVAL_VECTOR_TOP_K = _env_int("RETRIEVAL_VECTOR_TOP_K", 12)
RETRIEVAL_BM25_TOP_K = _env_int("RETRIEVAL_BM25_TOP_K", 12)
RETRIEVAL_FUSION_TOP_K = _env_int("RETRIEVAL_FUSION_TOP_K", 10)
RETRIEVAL_RERANK_TOP_N = _env_int("RETRIEVAL_RERANK_TOP_N", 6)
RETRIEVAL_NUM_QUERIES = _env_int("RETRIEVAL_NUM_QUERIES", 1)
RETRIEVAL_VECTOR_WEIGHT = _env_float("RETRIEVAL_VECTOR_WEIGHT", 0.6)
RETRIEVAL_BM25_WEIGHT = _env_float("RETRIEVAL_BM25_WEIGHT", 0.4)
CONTEXT_COMPRESSION_PERCENTILE = _env_float("CONTEXT_COMPRESSION_PERCENTILE", 0.5)
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")


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
    _bm25_nodes_cache = None
    _base_hybrid_retriever = None


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
) -> BM25Retriever | None:
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
    """Pre-warm BM25 index, fusion retriever, and reranker at startup."""
    get_base_hybrid_retriever(index)
    create_node_postprocessors()
    logger.info("Retrieval stack initialized")


def create_hybrid_retriever(
    index: VectorStoreIndex,
    *,
    metadata_filters: MetadataFilters | None = None,
    profile: UserProfile | None = None,
) -> BaseRetriever:
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


def create_node_postprocessors() -> list[BaseNodePostprocessor]:
    global _node_postprocessors
    if _node_postprocessors is not None:
        return _node_postprocessors

    _node_postprocessors = [
        _create_reranker(),
        SentenceEmbeddingOptimizer(
            embed_model=Settings.embed_model,
            percentile_cutoff=CONTEXT_COMPRESSION_PERCENTILE,
        ),
        LongContextReorder(),
    ]
    return _node_postprocessors


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