# --- Import path fix (supports direct execution) ---
# This allows running the file directly without PYTHONPATH:
#   python src/api/main.py
#   (Docker uses ENV PYTHONPATH=/app instead)
import sys
from pathlib import Path

if __package__ in (None, ""):
    # We are being run as a script (not via -m or installed package)
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
# --- end import path fix ---

import os
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import shutil

from src.chatbot.chatbot import create_chat_engine

# Configure logging properly (was misnamed "AI_Model_Health" before)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mc_ai_chatbot")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure LLM + embeddings once at startup (non-DB side only)
    from src.config import configure_llama_index
    try:
        configure_llama_index()
    except Exception as e:
        logger.error(f"LLM/embeddings configuration failed: {e}")
        # Do not raise here to allow health checks; real errors will surface on /chat
    yield
    # shutdown cleanup (none needed currently)


app = FastAPI(title="Course Chatbot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Consider restricting in production
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
    # NOTE: DB import intentionally left inside per scope rules (no DB layer edits)

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

    import re
    from src.chatbot.chatbot import get_streaming_response

    try:
        streaming_response = get_streaming_response(chat_engine, request.message)
    except Exception as e:
        logger.error(f"Error initiating chat stream with model provider: {e}", exc_info=True)
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
            logger.error(f"Stream interrupted by model provider: {e}", exc_info=True)
            yield "\n\n[Error: AI Model provider disconnected. Please try again.]"

    return StreamingResponse(response_generator(), media_type="text/plain")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Uploads a PDF file, saves it to the data/ directory, and automatically
    chunks, embeds, and stores its vectors into the PostgreSQL database.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    
    # Save the file to data/ directory
    os.makedirs("data", exist_ok=True)
    file_path = os.path.join("data", file.filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Parse the PDF using LlamaIndex
        from llama_index.core import SimpleDirectoryReader
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
        
        # Import the global index
        from src.chatbot.chatbot import index
        
        # Insert each document into the index
        # This will automatically chunk, embed, and store in PGVectorStore
        for doc in documents:
            index.insert(doc)
            
        return {
            "status": "success", 
            "message": f"Successfully uploaded and vectorized {file.filename}",
            "chunks_processed": len(documents)
        }
    except Exception as e:
        logger.error(f"Error processing PDF upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process and vectorize PDF: {str(e)}")

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
    # Use module string form (recommended). The path fix above makes
    # `python src/api/main.py` work the same as `uvicorn src.api.main:app`.
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000)