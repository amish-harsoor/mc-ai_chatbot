import os
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai_like import OpenAILike
from llama_index.llms.groq import Groq

load_dotenv()

def configure_llama_index():
    """
    Call this once at startup to configure the embedding model and LLM globally.
    After calling this, all LlamaIndex components will automatically use these settings.
    """

    Settings.embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")

    llm_provider = os.getenv("LLM_PROVIDER", "openrouter").lower()

    if llm_provider == "groq":
        # Groq LLM configuration
        Settings.llm = Groq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.3,
            max_tokens=1024,
            additional_kwargs={"top_p": 1},
        )
        print(f"LlamaIndex configured with Groq (model: llama-3.3-70b-versatile)")
    else:
        # Default to OpenRouter (OpenAILike)
        Settings.llm = OpenAILike(
            model="nvidia/nemotron-3-nano-30b-a3b:free",
            api_base="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            temperature=0.3,
            max_tokens=1024,
            is_chat_model=True,
        )
        print(f"LlamaIndex configured with OpenRouter (model: nvidia/nemotron-3-nano-30b-a3b:free)")

    Settings.chunk_size = 512
    Settings.chunk_overlap = 50