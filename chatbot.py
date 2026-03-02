import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core.memory import ChatMemoryBuffer
from config import configure_llama_index

load_dotenv()
configure_llama_index()

def load_index():
    """
    Loads the index from PostgreSQL vector store.
    """
    vector_store = PGVectorStore.from_params(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "mc_chatbot"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        table_name="vectors",
        embed_dim=384,
    )
    return VectorStoreIndex.from_vector_store(vector_store)

print("Loading index from PostgreSQL...")
index = load_index()
print("Index loaded and ready.")

def create_chat_engine():
    """
    Creates a new chat engine with its own fresh memory.
    Call this once per user session to give each user their own conversation history.

    ChatMemoryBuffer keeps track of conversation history but caps it at token_limit
    tokens. This prevents the prompt from growing infinitely as the chat gets longer.
    """
    memory = ChatMemoryBuffer.from_defaults(token_limit=3000)

    return index.as_chat_engine(
        chat_mode="context",
        memory=memory,
        system_prompt=(
    "You are the 'MC Course Advisor', a professional guide for Management Concepts. Keep responses **compact** for a small UI.\n\n"
    
    "**Core Guidelines:**\n"
    "1. **Brevity is King**: Keep entire responses under 100 words. Start with a 1-sentence answer, then use **bullet points** or a **Compact Markdown Table** for details and lists.\n"
    "2. **Visual Clarity**: Use bolding for Course IDs. Tables should only have 2-3 essential columns (e.g., ID, Title, Credits).\n"
    "3. **Zero Filler**: Do NOT use introductory phrases like 'Based on the information provided' or 'I found the following'. Jump straight to the data.\n"
    "4. **Missing Info**: If data is missing, say: '[Detail] not found in documents. Visit managementconcepts.com for live info.'\n"
    "5. **Proactive & Short**: Always end with a brief question on a **new line** (e.g., '\n\nCheck price?' or '\n\nSee schedule?') to keep it separate from the main answer.\n"
    "6. **Clickable Links**: Always provide Markdown links for actions. Format: `[Register Now](https://www.managementconcepts.com/course/ID)` or `[Course Details](URL)`. If a specific URL isn't in the documents, use the `managementconcepts.com/course/[ID]` pattern as a fallback.\n\n"
    
    "**Data Rules:**\n"
    "- Distinguish credits (CPE/CLP/PDU) clearly but briefly.\n"
    "- For FAQs, provide a 1-sentence direct answer.\n\n"
    
    "Direct. Compact. Helpful."
        ),
        similarity_top_k=6,  # Increased for better coverage
        verbose=False,
    )

def get_response(chat_engine, user_message: str) -> str:
    """
    Send a message to the chat engine and get a response.
    """
    response = chat_engine.chat(user_message)
    return str(response)

def get_streaming_response(chat_engine, user_message: str):
    """
    Returns a streaming response object.
    """
    return chat_engine.stream_chat(user_message)