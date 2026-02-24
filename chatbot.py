import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.core.memory import ChatMemoryBuffer
from config import configure_llama_index

load_dotenv()
configure_llama_index()

def load_index():
    """
    Loads the index from the local './storage' directory.
    """
    if not os.path.exists("./storage"):
        raise FileNotFoundError("Storage directory not found. Please run ingest.py first!")
        
    storage_context = StorageContext.from_defaults(persist_dir="./storage")
    return load_index_from_storage(storage_context)

print("Loading index from local storage...")
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
            "You are a knowledgeable AI Assistant for Management Concepts. "
            "Your priority is to provide accurate but concise information based *only* on the provided context.\n\n"
            "**Guidelines:**\n"
            "1. **Efficiency First**: Provide direct answers. Avoid introductory fluff and long-winded explanations unless specifically asked for detail.\n"
            "2. **Be Specific but Brief**: If the user asks about a course, provide key details (ID, Duration, Credits) in a tight, structured format.\n"
            "3. **Structured Response**: Use bullet points and bolding for quick scanning. Keep paragraphs short (2-3 sentences max).\n"
            "4. **Source-Only**: If the answer isn't in the context, say: 'I couldn't find specific details for that in our current documents.'\n\n"
            "The user values accuracy delivered with brevity and speed."
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