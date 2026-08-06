import logging
import os

from dotenv import load_dotenv
from llama_index.core import Settings

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


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


def _chat_max_tokens(default: int = 700) -> int:
    return int(os.getenv("CHAT_MAX_TOKENS", str(default)))


def _create_openai_llm():
    """Direct OpenAI API chat model (primary)."""
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for LLM_PROVIDER=openai")

    from llama_index.llms.openai import OpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    kwargs: dict = {
        "model": model,
        "api_key": api_key,
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
        "max_tokens": _chat_max_tokens(700),
    }
    api_base = (os.getenv("OPENAI_API_BASE") or "").strip()
    if api_base:
        kwargs["api_base"] = api_base

    llm = OpenAI(**kwargs)
    logger.info("LLM ready: OpenAI (%s)", model)
    return llm


def _create_openrouter_llm():
    """OpenRouter chat model (fallback)."""
    api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required for LLM_PROVIDER=openrouter")

    from llama_index.llms.openai_like import OpenAILike

    model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free")
    llm = OpenAILike(
        model=model,
        api_base="https://openrouter.ai/api/v1",
        api_key=api_key,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        # Same default budget as OpenAI/Groq so fallback replies are not truncated shorter.
        max_tokens=_chat_max_tokens(700),
        is_chat_model=True,
    )
    logger.info("LLM ready: OpenRouter (%s)", model)
    return llm


def _create_groq_llm():
    """Groq chat model (fallback)."""
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required for LLM_PROVIDER=groq")

    from llama_index.llms.groq import Groq

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    llm = Groq(
        model=model,
        api_key=api_key,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        max_tokens=_chat_max_tokens(700),
        additional_kwargs={"top_p": 1},
    )
    logger.info("LLM ready: Groq (%s)", model)
    return llm


# Default chain: OpenAI primary; existing providers remain as fallbacks.
_DEFAULT_LLM_PROVIDER = "openai"
_DEFAULT_LLM_FALLBACKS = "openrouter,groq"
_KNOWN_LLM_PROVIDERS = frozenset({"openai", "openrouter", "groq"})


def _llm_factories() -> dict:
    """Resolve factories at call time so tests can patch individual creators."""
    return {
        "openai": _create_openai_llm,
        "openrouter": _create_openrouter_llm,
        "groq": _create_groq_llm,
    }


def _llm_provider_chain() -> list[str]:
    """Primary provider first, then configured fallbacks (deduped, order preserved)."""
    primary = (os.getenv("LLM_PROVIDER") or _DEFAULT_LLM_PROVIDER).strip().lower()
    if primary == "auto":
        # Prefer OpenAI when available, then legacy providers.
        raw_fallbacks = os.getenv(
            "LLM_FALLBACK_PROVIDERS",
            f"{_DEFAULT_LLM_PROVIDER},{_DEFAULT_LLM_FALLBACKS}",
        )
        chain = [p.strip().lower() for p in raw_fallbacks.split(",") if p.strip()]
    else:
        raw_fallbacks = os.getenv("LLM_FALLBACK_PROVIDERS", _DEFAULT_LLM_FALLBACKS)
        fallbacks = [p.strip().lower() for p in raw_fallbacks.split(",") if p.strip()]
        chain = [primary, *[p for p in fallbacks if p != primary]]

    seen: set[str] = set()
    ordered: list[str] = []
    for name in chain:
        if name in seen:
            continue
        if name not in _KNOWN_LLM_PROVIDERS:
            logger.warning("Unknown LLM provider %r — skipping", name)
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def create_llm(provider: str):
    """Build an LLM instance for a single provider name (no Settings mutation)."""
    key = (provider or "").strip().lower()
    factory = _llm_factories().get(key)
    if factory is None:
        raise RuntimeError(
            f"Unknown LLM_PROVIDER={provider!r}. "
            f"Use one of: {', '.join(sorted(_KNOWN_LLM_PROVIDERS))}."
        )
    return factory()


def configure_llm() -> None:
    """Configure chat LLM: OpenAI primary, OpenRouter/Groq as config-time fallbacks.

    Fallback runs only at configure time (missing key / import failure). Mid-request
    provider errors are not retried against the next provider — restart or fix keys.

    Embeddings are unchanged (see configure_embeddings). Set:
      LLM_PROVIDER=openai
      OPENAI_API_KEY=...
      OPENAI_MODEL=gpt-4o-mini
      LLM_FALLBACK_PROVIDERS=openrouter,groq
    """
    chain = _llm_provider_chain()
    if not chain:
        raise RuntimeError(
            "No valid LLM providers configured. "
            "Set LLM_PROVIDER to openai, openrouter, or groq."
        )

    errors: list[str] = []
    for name in chain:
        try:
            Settings.llm = create_llm(name)
            if errors:
                logger.warning(
                    "LLM primary/earlier providers failed; using %s. Prior errors: %s",
                    name,
                    " | ".join(errors),
                )
            else:
                logger.info("LLM provider selected: %s", name)
            return
        except Exception as exc:
            msg = f"{name}: {exc}"
            errors.append(msg)
            logger.warning("LLM provider %s unavailable: %s", name, exc)

    raise RuntimeError(
        "All LLM providers failed. Tried: "
        + ", ".join(chain)
        + ". Errors: "
        + " | ".join(errors)
        + ". Set OPENAI_API_KEY (preferred), or OPENROUTER_API_KEY / GROQ_API_KEY for fallbacks."
    )


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
        "Retrieval config: vector_top_k=%s, rerank=%s, num_queries=%s",
        os.getenv("RETRIEVAL_VECTOR_TOP_K", "8"),
        os.getenv("ENABLE_RERANK", "true"),
        os.getenv("RETRIEVAL_NUM_QUERIES", "1"),
    )