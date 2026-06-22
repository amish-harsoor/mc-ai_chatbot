import os
import re
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core.memory import ChatMemoryBuffer
from src.config import configure_llama_index
import logging

# Configure logging
logger = logging.getLogger("AI_Model_Health")

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

def create_chat_engine(chat_history=None):
    """
    Creates a new chat engine with its own fresh memory.
    Call this once per user session to give each user their own conversation history.

    ChatMemoryBuffer keeps track of conversation history but caps it at token_limit
    tokens. This prevents the prompt from growing infinitely as the chat gets longer.
    """
    if chat_history is None:
        chat_history = []
    
    memory = ChatMemoryBuffer.from_defaults(chat_history=chat_history, token_limit=3000)

    return index.as_chat_engine(
        chat_mode="condense_plus_context", # Uses chat history to generate a better search query, ensuring department & experience are searched for
        memory=memory,
        system_prompt=('''You are Course Advisor, a friendly and helpful assistant guiding users to find the best courses from Management Concepts. Act like a normal, conversational AI assistant, but heavily specialize in recommending and discussing our courses.

**Core Responsibilities:**
- Engage in natural, friendly conversation with the user.
- Use the provided database context to accurately answer questions and recommend courses.
- If a user asks for something outside the database or if no relevant courses are found, politely explain that you can only help with courses available in the Management Concepts catalog, and offer to help them find something else. DO NOT say 'Information notavailable.'

**Course Output Format:**
When recommending or listing courses, always use this clear format for the courses themselves, but feel free to add conversational text before and after the recommendations:

**[COURSE_ID]** [Course Title](https://www.managementconcepts.com/product/{course_id})
Duration: ...
Cost: ...
Description: ...

Always use the URL format: https://www.managementconcepts.com/product/{course_id}

**Response Guidelines:**
- Be conversational, warm, and helpful. Feel free to greet the user and use pleasantries.
- Provide explanations and context for your recommendations. Let the user know *why* a course is a good fit.
- Recommend 3-5 courses at a time unless asked for more.
- If the user sends a message starting with "My experience level" or "My department", reply ONLY with the word "Acknowledged." and wait for their next input.
- When the user sends a message starting with "My career goal", this means you have their full profile. Go ahead and enthusiastically recommend some courses based on their experience, department, and goal!

**CRITICAL: Using User Preferences:**
Throughout the chat, keep the user's provided profile data (Experience Level, Department, Career Goal) in mind. Tailor your conversations and course recommendations to align perfectly with their specific background and goals.

**CRITICAL RULE: NEVER RETURN AN EMPTY RESPONSE.** If you are unsure or cannot find a specific course, acknowledge the user's input and provide a helpful, conversational response or ask a follow-up question. Under no circumstances should you output a blank message.
'''),
        similarity_top_k=6,
        verbose=True,
    )

def get_response(chat_engine, user_message: str) -> str:
    """
    Send a message to the chat engine and get a response.
    """
    try:
        response = chat_engine.chat(user_message)
    except Exception as e:
        logger.error(f"AI Model Health Check Failed: Error getting response from model provider. Details: {e}", exc_info=True)
        return "I'm currently experiencing a connection issue with my AI brain. Please try again in a moment."

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