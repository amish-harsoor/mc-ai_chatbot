import logging
import os

from dotenv import load_dotenv
from llama_index.core import Settings

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


_FASTEMBED_INSTALL_HINT = (
    "Install FastEmbed (no PyTorch): "
    "python -m pip install \"fastembed>=0.3,<0.7\" "
    "\"llama-index-embeddings-fastembed>=0.2,<0.4\""
)


def _preload_torch() -> None:
    """Import PyTorch before other native libs to avoid Windows DLL init failures."""
    import torch  # noqa: F401


def _preload_onnx_runtime() -> None:
    """Import ONNX before other native libs to avoid Windows DLL init failures."""
    import onnxruntime  # noqa: F401


def _create_huggingface_model():
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    return HuggingFaceEmbedding(model_name=DEFAULT_EMBED_MODEL)


def _create_fastembed_model():
    from llama_index.embeddings.fastembed import FastEmbedEmbedding

    return FastEmbedEmbedding(model_name=DEFAULT_EMBED_MODEL)


def _create_openrouter_embed_model():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required when EMBED_PROVIDER=openrouter")

    from llama_index.embeddings.openai import OpenAIEmbedding

    # OpenAIEmbedding expects OpenAI-style model ids (no openai/ prefix).
    model_name = os.getenv("OPENROUTER_EMBED_MODEL", "text-embedding-3-small")
    if "/" in model_name:
        model_name = model_name.split("/", 1)[-1]

    dimensions = int(os.getenv("EMBED_DIM", "384"))
    kwargs = {
        "api_key": api_key,
        "api_base": "https://openrouter.ai/api/v1",
        "model": model_name,
        "dimensions": dimensions,
    }
    model = OpenAIEmbedding(**kwargs)
    logger.info("Embeddings: OpenRouter (%s, dim=%s)", model_name, dimensions)
    return model


def _create_openai_embed_model():
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY or OPENROUTER_API_KEY is required when EMBED_PROVIDER=openai"
        )
    from llama_index.embeddings.openai import OpenAIEmbedding

    api_base = os.getenv("OPENAI_API_BASE")
    kwargs = {
        "api_key": api_key,
        "model": os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
    }
    if api_base:
        kwargs["api_base"] = api_base
    embed_dim = os.getenv("EMBED_DIM")
    if embed_dim:
        kwargs["dimensions"] = int(embed_dim)
    model = OpenAIEmbedding(**kwargs)
    logger.info("Embeddings: OpenAI (%s)", kwargs["model"])
    return model


def _create_embed_model():
    """Create an embedding model without importing torch at module load time."""
    provider = os.getenv("EMBED_PROVIDER", "huggingface").lower()

    if provider == "huggingface":
        try:
            model = _create_huggingface_model()
            logger.info("Embeddings: HuggingFace (%s)", DEFAULT_EMBED_MODEL)
            return model
        except Exception as exc:
            raise RuntimeError(
                f"HuggingFace embeddings failed ({exc}). "
                "Try reinstalling CPU PyTorch: "
                "python -m pip install --force-reinstall torch --index-url "
                "https://download.pytorch.org/whl/cpu"
            ) from exc

    if provider == "fastembed":
        model = _create_fastembed_model()
        logger.info("Embeddings: FastEmbed (%s)", DEFAULT_EMBED_MODEL)
        return model

    if provider == "openrouter":
        return _create_openrouter_embed_model()

    if provider == "openai":
        return _create_openai_embed_model()

    raise RuntimeError(
        f"Unknown EMBED_PROVIDER={provider!r}. "
        "Use huggingface (default), fastembed, openrouter, or openai."
    )


def configure_embeddings() -> None:
    provider = os.getenv("EMBED_PROVIDER", "huggingface").lower()
    if provider == "huggingface":
        try:
            _preload_torch()
        except Exception:
            pass
    elif provider == "fastembed":
        try:
            _preload_onnx_runtime()
        except Exception:
            pass
    Settings.embed_model = _create_embed_model()


def configure_chunk_settings() -> None:
    Settings.chunk_size = int(os.getenv("CHUNK_SIZE", "512"))
    Settings.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "50"))


def configure_llm() -> None:
    llm_provider = os.getenv("LLM_PROVIDER", "openrouter").lower()

    if llm_provider == "groq":
        from llama_index.llms.groq import Groq

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        Settings.llm = Groq(
            model="llama-3.3-70b-versatile",
            api_key=api_key,
            temperature=0.3,
            max_tokens=1024,
            additional_kwargs={"top_p": 1},
        )
        logger.info("LlamaIndex configured with Groq (model: llama-3.3-70b-versatile)")
        return

    from llama_index.llms.openai_like import OpenAILike

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is required (or set LLM_PROVIDER=groq + GROQ_API_KEY)"
        )
    Settings.llm = OpenAILike(
        model="meta-llama/llama-3.1-8b-instruct",
        api_base="https://openrouter.ai/api/v1",
        api_key=api_key,
        temperature=0.3,
        max_tokens=1024,
        is_chat_model=True,
    )
    logger.info("LlamaIndex configured with OpenRouter (model: meta-llama/llama-3.1-8b-instruct)")


def configure_for_ingest() -> None:
    """Embeddings + chunk settings only (no LLM required for ingestion)."""
    configure_embeddings()
    configure_chunk_settings()
    logger.info(
        "Ingest config: chunk_size=%s, semantic_chunking=%s",
        Settings.chunk_size,
        os.getenv("INGEST_USE_SEMANTIC_CHUNKING", "false"),
    )


def configure_llama_index() -> None:
    """Full stack: embeddings, chunk settings, and LLM."""
    configure_for_ingest()
    configure_llm()
    logger.info(
        "Retrieval config: hybrid=%s, rerank=%s, query_expansion=%s",
        os.getenv("RETRIEVAL_VECTOR_TOP_K", "12"),
        os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
        os.getenv("RETRIEVAL_NUM_QUERIES", "3"),
    )