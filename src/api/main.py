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
from typing import Optional
import shutil

from src.chatbot.chatbot import get_or_create_chat_engine

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

    from src.db.course_prices import init_course_prices_table
    from src.db.session_manager import init_db
    try:
        init_db()
        init_course_prices_table()
        logger.info("chat_messages and course_prices tables initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    yield
    from src.chatbot.chatbot import clear_session_engine_cache
    from src.chatbot.retrieval import clear_retrieval_caches

    clear_session_engine_cache()
    clear_retrieval_caches()
    logger.info("Session and retrieval caches cleared on shutdown")


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
    display_message: Optional[str] = None
    silent_response: bool = False
    metadata: Optional[dict] = None

class SaveMessageRequest(BaseModel):
    role: str
    content: str
    display_content: Optional[str] = None
    metadata: Optional[dict] = None

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


def _is_partial_onboarding(metadata: dict | None) -> bool:
    """Onboarding selections before profile is complete should not call the LLM."""
    if not metadata:
        return False
    if metadata.get("profile_complete"):
        return False
    return metadata.get("step") in ("experience", "department")


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    from src.db.session_manager import get_llm_session_history, save_message
    # NOTE: DB import intentionally left inside per scope rules (no DB layer edits)

    # Try to parse uuid just to validate format if we want, or just proceed
    try:
        uuid.UUID(request.session_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID format."
        )

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if _is_partial_onboarding(request.metadata):
        user_metadata = dict(request.metadata) if request.metadata else {}
        save_message(
            request.session_id,
            "user",
            request.message,
            display_content=request.display_message or request.message,
            metadata=user_metadata or None,
        )
        return StreamingResponse(iter(()), media_type="text/plain")

    chat_history = get_llm_session_history(request.session_id)
    chat_engine = get_or_create_chat_engine(
        request.session_id,
        chat_history,
        latest_message=request.message,
        request_metadata=request.metadata,
    )

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
            user_metadata = dict(request.metadata) if request.metadata else {}
            save_message(
                request.session_id,
                'user',
                request.message,
                display_content=request.display_message or request.message,
                metadata=user_metadata or None,
            )
            assistant_metadata = {"visible": not request.silent_response}
            save_message(
                request.session_id,
                'assistant',
                full_response,
                display_content=full_response,
                metadata=assistant_metadata,
            )
        except Exception as e:
            logger.error(f"Stream interrupted by model provider: {e}", exc_info=True)
            yield "\n\n[Error: AI Model provider disconnected. Please try again.]"

    return StreamingResponse(response_generator(), media_type="text/plain")

@app.get("/health")
async def health():
    return {"status": "ok"}

SUPPORTED_UPLOAD_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}


def _save_uploaded_file(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(SUPPORTED_UPLOAD_EXTENSIONS))}",
        )

    os.makedirs("data", exist_ok=True)
    file_path = os.path.join("data", file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path


@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Backward-compatible PDF upload endpoint."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    return await upload_document(file)


@app.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):
    """
    Uploads a supported document, saves it to data/, and incrementally ingests it
    with semantic chunking, metadata extraction, and deduplication.
    """
    from src.ingestion.pipeline import IngestionPipeline
    from src.chatbot.chatbot import index

    try:
        file_path = _save_uploaded_file(file)
        pipeline = IngestionPipeline(index=index)
        result = pipeline.ingest_file(file_path, force=True)

        return {
            "status": "success" if result.action == "indexed" else result.action,
            "message": result.message or f"Processed {file.filename}",
            "source_path": result.source_path,
            "chunks_processed": result.chunk_count,
            "skipped_duplicate_chunks": result.skipped_duplicate_chunks,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process and vectorize document: {str(e)}",
        )


class IngestUrlRequest(BaseModel):
    url: str
    force: bool = False


@app.post("/ingest-url")
async def ingest_url_endpoint(request: IngestUrlRequest):
    """Fetches a web page and ingests it into the vector store."""
    from src.ingestion.pipeline import IngestionPipeline
    from src.chatbot.chatbot import index

    if not request.url.strip().lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    try:
        pipeline = IngestionPipeline(index=index)
        result = pipeline.ingest_url(request.url.strip(), force=request.force)
        return {
            "status": "success" if result.action == "indexed" else result.action,
            "message": result.message,
            "source_path": result.source_path,
            "chunks_processed": result.chunk_count,
            "skipped_duplicate_chunks": result.skipped_duplicate_chunks,
        }
    except Exception as e:
        logger.error(f"Error ingesting URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to ingest URL: {str(e)}")

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

@app.post("/session/{session_id}/message")
async def save_session_message(session_id: str, request: SaveMessageRequest):
    from src.db.session_manager import save_message

    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID format."
        )

    if request.role not in ("user", "assistant"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'assistant'.")

    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty.")

    save_message(
        session_id,
        request.role,
        request.content,
        display_content=request.display_content or request.content,
        metadata=request.metadata,
    )
    return {"status": "ok", "session_id": session_id}


if __name__ == "__main__":
    import uvicorn
    # Use module string form (recommended). The path fix above makes
    # `python src/api/main.py` work the same as `uvicorn src.api.main:app`.
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000)