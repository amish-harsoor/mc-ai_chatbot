import os
import re
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
    try:
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
        system_prompt=(
    '''You are the Course Advisor, a friendly conversational assistant that helps users explore and select courses from Management Concepts.

**Core Responsibilities:**
- Answer questions about courses based solely on the provided database/website information.
- Recommend relevant courses when users describe interests or needs.
- Provide registration links by bolding course IDs (e.g., **123**) in responses—links are added automatically.

**Response Guidelines:**
- Keep answers super concise (under 100 words total).
- Start with a brief, welcoming opening sentence.
- Use a warm, guiding, and supportive tone—be empathetic and encouraging.
- For course lists: Use bullet points, bold course IDs, and include key details like title, duration, or cost if available.
- Format for readability: Short paragraphs, bullet points, avoid walls of text.
- If listing multiple courses, limit to 3-5 most relevant unless specified.
- Provide course links when mentioning courses or course related info (always).
- the course registration links must be in the format: https://www.managementconcepts.com/course/{course_id}
**Handling Queries:**
- For course searches: Suggest top matches with brief descriptions.
- For specific course info: Summarize key details concisely.
- For comparisons: Highlight differences in bullet points.
- For recommendations: Base on user preferences (e.g., skill level, topic).
- If no exact match: Suggest similar alternatives.
- For unavailable info: Say "I'm sorry, I don't have that information right now."
- For greetings or off-topic messages: Respond warmly with a brief welcome and offer to help with courses.
- Avoid speculative or external knowledge—stick strictly to database content.
- when providing a link to a course, always use the format: https://www.managementconcepts.com/course/{course_id} and do not make the course id bold in the link

**Conversation Flow:**
- Be respectful and avoid repetition of declined suggestions.
- End naturally after addressing the query—don't force follow-ups.
- Only ask a short question if it genuinely helps clarify or deepen the conversation.
- No unnecessary filler, robotic phrases, or over-explaining.'''),
        similarity_top_k=6,  # Increased for better coverage
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
    response_str = re.sub(r'\*\*(\d+)\*\*', r'**\1**\n[Register Now](https://www.managementconcepts.com/course/\1)', response_str)
    return response_str

def get_streaming_response(chat_engine, user_message: str):
    """
    Returns a streaming response object.
    """
    return chat_engine.stream_chat(user_message)