import os
import re
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core.memory import ChatMemoryBuffer
from src.config import configure_llama_index

load_dotenv()
configure_llama_index()

def load_index():
    """
    Loads the index from PostgreSQL vector store (Supabase or Local based on USE_SUPABASE).
    """
    try:
        use_supabase = os.getenv("USE_SUPABASE", "false").lower() == "true"
        
        if use_supabase:
            print("Using Supabase database...")
            vector_store = PGVectorStore.from_params(
                host=os.getenv("SUPABASE_HOST", "localhost"),
                port=int(os.getenv("SUPABASE_PORT", "5432")),
                database=os.getenv("SUPABASE_DATABASE", "postgres"),
                user=os.getenv("SUPABASE_USER", "postgres"),
                password=os.getenv("SUPABASE_PASSWORD"),
                table_name="data_data_vectors",
                embed_dim=384,
            )
        else:
            print("Using local database...")
            vector_store = PGVectorStore.from_params(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv("DB_NAME", "mc_chatbot"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD"),
                table_name="data_vectors",
                embed_dim=384,
            )
        
        return VectorStoreIndex.from_vector_store(vector_store)
    except Exception as e:
        print(f"Error loading index: {e}")
        raise

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
        system_prompt=('''You are Course Advisor, a friendly assistant helping users explore and select courses from Management Concepts.

**Core Responsibilities:**
Answer questions ONLY using courses explicitly present in the provided database.
Recommend courses only if they appear in the database with a valid course ID.
Never invent, guess, or approximate course names, IDs, durations, or costs.

**Strict Rules — No Exceptions:**
If a course is not in the database: do not show it. Do not mention it. Do not suggest it exists elsewhere.
If information is unavailable or not in the database: respond with exactly one line — "Information not available." Nothing more.
Never speculate, extrapolate, or use any knowledge outside the provided database.
Never fill silence with explanations, apologies, or alternatives unless an alternative actually exists in the database.

**Course Output Format:**
When recommending or listing courses, use this exact format for each course:

**[COURSE_ID]** [Course Title](https://www.managementconcepts.com/product/{course_id})
Duration: ...
Cost: ...
Description: ...

Each detail on its own line. No prose wrapping around it.
Always use the URL format: https://www.managementconcepts.com/product/{course_id} — never /course/.

**Response Rules:**
Keep answers concise (under 100 words excluding course listings).
Do NOT greet or use pleasantries. Go straight to answering the query.
For multiple items: always use bullet points. Prose only for single-item answers.
Limit course recommendations to 3–5 unless user asks for more.
For comparisons: highlight differences in bullet points.
Answer the query, then stop. Do not force follow-ups.
Only ask a clarifying question if it genuinely helps narrow a recommendation.
Do not repeat suggestions the user has already declined.
Context messages starting with "My experience level", "My department", or "My career goal" are user profile data — acknowledge them with a single sentence only, no course suggestions yet.
'''),
    similarity_top_k=6,
    verbose=False,
)

def get_response(chat_engine, user_message: str) -> str:
    """
    Send a message to the chat engine and get a response.
    """
    response = chat_engine.chat(user_message)
    response_str = str(response)
    if not response_str.strip():
        # Fallback for empty responses, e.g., off-topic queries
        response_str = "Hey there! I'm here to help with courses from Management Concepts. What can I assist you with today?"
    # Add "Register Now" link after each bolded course ID
    response_str = re.sub(r'\*\*(\d+)\*\*', r'**\1**\n[Register Now](https://www.managementconcepts.com/product/\1)', response_str)
    return response_str

def get_streaming_response(chat_engine, user_message: str):
    """
    Returns a raw streaming response object.
    Post-processing (e.g. Register Now link injection) is handled by the caller (main.py)
    after buffering the full response text.
    """
    return chat_engine.stream_chat(user_message)