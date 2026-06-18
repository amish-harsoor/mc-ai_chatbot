import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AI_Model_Health")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from src.chatbot.chatbot import create_chat_engine, get_response

app = FastAPI(title="Course Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartSessionResponse(BaseModel):
    session_id: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    answer: str
    session_id: str

@app.post("/session/start", response_model=StartSessionResponse)
async def start_session():
    """
    Call this when a user opens the chat. It creates a new chat engine
    with fresh memory and returns a session_id that the frontend must
    include in every subsequent /chat request.
    """
    session_id = str(uuid.uuid4())
    return StartSessionResponse(session_id=session_id)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    from src.db.session_manager import get_session_history, save_message
    from src.chatbot.chatbot import create_chat_engine
    
    # Try to parse uuid just to validate format if we want, or just proceed
    try:
        uuid.UUID(request.session_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID format."
        )

    chat_history = get_session_history(request.session_id)
    chat_engine = create_chat_engine(chat_history)
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    from src.chatbot.chatbot import get_streaming_response
    import re

    try:
        streaming_response = get_streaming_response(chat_engine, request.message)
    except Exception as e:
        logger.error(f"AI Model Health Check Failed: Error initiating chat stream with model provider. Details: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="AI Model provider is currently unavailable. Please try again later.")

    def response_generator():
        buffer = ""
        full_response = ""
        try:
            for token in streaming_response.response_gen:
                buffer += token
                full_response += token
                
                # Keep a buffer of ~50 characters for lookahead/regex safety
                if len(buffer) > 100:
                    # Split at the last space before the last 50 characters to avoid breaking words
                    split_idx = buffer.rfind(' ', 0, len(buffer) - 50)
                    if split_idx == -1:
                        split_idx = len(buffer) - 50
                    
                    chunk = buffer[:split_idx]
                    buffer = buffer[split_idx:]
                    
                    processed = re.sub(
                        r'\*\*(\d+)\*\*(?!\s*\n\[Register Now\])',
                        r'**\1**\n[Register Now](https://www.managementconcepts.com/product/\1)',
                        chunk
                    )
                    yield processed

            if buffer:
                processed = re.sub(
                    r'\*\*(\d+)\*\*(?!\s*\n\[Register Now\])',
                    r'**\1**\n[Register Now](https://www.managementconcepts.com/product/\1)',
                    buffer
                )
                yield processed
                
            if not full_response.strip():
                if "career goal" in request.message.lower():
                    fallback = "I'm looking at our catalog right now, and we have excellent courses for that! Could you specify if you prefer online or in-person training so I can narrow it down?"
                else:
                    fallback = "I'm here to help with courses from Management Concepts! Please let me know what else you'd like to explore."
                yield fallback
                full_response = fallback
                
            # After streaming is complete, save the messages to the database
            save_message(request.session_id, 'user', request.message)
            save_message(request.session_id, 'assistant', full_response)
        except Exception as e:
            logger.error(f"AI Model Health Check Failed: Stream interrupted by model provider. Details: {e}", exc_info=True)
            yield "\n\n[Error: AI Model provider disconnected. Please try again.]"

    return StreamingResponse(response_generator(), media_type="text/plain")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/session/{session_id}/history")
async def get_history(session_id: str):
    from src.db.session_manager import get_session_history_raw
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID format."
        )
    
    messages = get_session_history_raw(session_id)
    return {"session_id": session_id, "messages": messages}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)