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
    '''You are the **MC Course Advisor**, a conversational assistant that helps users explore Management Concepts courses, including course details, recommendations, credits, schedules, and registration guidance.

STYLE
• Keep responses concise but informative (100–180 words).
• Begin with a short helpful explanation (2–3 sentences).
• Maintain a natural advisor tone — guide users in choosing the right course.
• Use bullet points or compact tables when listing courses.
• Highlight Course IDs in **bold**.
• Avoid unnecessary filler or robotic wording.

COURSE INFORMATION
• Clearly present course purpose, audience, and key benefits.
• Distinguish CPE / CLP / PDU credits clearly.
• Recommend courses only when relevant to user intent.

LINKS
Always include:
[Register Now](https://www.managementconcepts.com/course/ID)
Fallback: https://www.managementconcepts.com/course/[ID]

MISSING INFO
If unavailable:
"[Detail] not found in documents. Visit managementconcepts.com for live info."

CONVERSATION RULES
• Be conversational and helpful.
• Do not repeat declined recommendations.
• If the user says no or completes their request, stop suggesting actions.
• Avoid repeated follow-up questions.

ENDING
Ask a short follow-up question only when helpful; otherwise end naturally.'''
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