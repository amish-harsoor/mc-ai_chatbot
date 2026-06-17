import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import uuid

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

    from src.chatbot.chatbot import get_streaming_response
    import re

    streaming_response = get_streaming_response(chat_engine, request.message)

    def response_generator():
        buffer = ""
        for token in streaming_response.response_gen:
            buffer += token
            
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

    return StreamingResponse(response_generator(), media_type="text/plain")

@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": len(active_sessions)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)