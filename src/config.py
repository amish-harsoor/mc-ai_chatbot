import os
import logging
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai_like import OpenAILike
from llama_index.llms.groq import Groq

load_dotenv()

logger = logging.getLogger(__name__)

def configure_llama_index():
    """
    Call this once at startup to configure the embedding model and LLM globally.
    After calling this, all LlamaIndex components will automatically use these settings.
    """
    Settings.embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")

    llm_provider = os.getenv("LLM_PROVIDER", "openrouter").lower()

    if llm_provider == "groq":
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
    else:
        # Default to OpenRouter via OpenAILike
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required (or set LLM_PROVIDER=groq + GROQ_API_KEY)")
        Settings.llm = OpenAILike(
            model="meta-llama/llama-3.1-8b-instruct",  # sane default matching README
            api_base="https://openrouter.ai/api/v1",
            api_key=api_key,
            temperature=0.3,
            max_tokens=1024,
            is_chat_model=True,
        )
        logger.info("LlamaIndex configured with OpenRouter (model: meta-llama/llama-3.1-8b-instruct)")

    Settings.chunk_size = 512
    Settings.chunk_overlap = 50