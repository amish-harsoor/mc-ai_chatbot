import os
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai_like import OpenAILike

load_dotenv()

def configure_llama_index():
    """
    Call this once at startup to configure the embedding model and LLM globally.
    After calling this, all LlamaIndex components will automatically use these settings.
    """

    Settings.embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")

    Settings.llm = OpenAILike(
        model="nvidia/nemotron-3-nano-30b-a3b:free",
        api_base="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        temperature=0.3,
        max_tokens=1024,
        is_chat_model=True,
    )

    Settings.chunk_size = 512
    Settings.chunk_overlap = 50