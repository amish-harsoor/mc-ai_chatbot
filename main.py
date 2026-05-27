from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from chatbot import create_chat_engine, get_response
import uuid
import os

app = FastAPI(title="Course Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_index():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return FileResponse(os.path.join(current_dir, "index.html"))

active_sessions: dict = {}

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
    active_sessions[session_id] = create_chat_engine()
    return StartSessionResponse(session_id=session_id)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    chat_engine = active_sessions.get(request.session_id)
    if not chat_engine:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please start a new session first."
        )

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    answer = get_response(chat_engine, request.message)
    return ChatResponse(answer=answer, session_id=request.session_id)

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    chat_engine = active_sessions.get(request.session_id)
    if not chat_engine:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please start a new session first."
        )

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    from chatbot import get_streaming_response
    import re

    streaming_response = get_streaming_response(chat_engine, request.message)

    def response_generator():
        # Buffer the full text so we can apply post-processing (e.g. Register Now links)
        full_text = ""
        for token in streaming_response.response_gen:
            full_text += token

        # Inject "Register Now" links after each bolded course ID that doesn't already have one
        processed = re.sub(
            r'\*\*(\d+)\*\*(?!\s*\n\[Register Now\])',
            r'**\1**\n[Register Now](https://www.managementconcepts.com/product/\1)',
            full_text
        )

        # Stream the processed text in reasonably sized chunks
        chunk_size = 64
        for i in range(0, len(processed), chunk_size):
            yield processed[i:i + chunk_size]

    return StreamingResponse(response_generator(), media_type="text/plain")

@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": len(active_sessions)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)