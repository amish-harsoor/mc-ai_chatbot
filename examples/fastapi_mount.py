"""
Mount the chatbot router inside an existing FastAPI application.

Run:
    uvicorn examples.fastapi_mount:app --reload --port 9000

Chatbot routes are served at /api/v1/chatbot/*
"""

from fastapi import FastAPI

from src.api.app import shutdown_chatbot, startup_chatbot
from src.api.router import router

app = FastAPI(title="My Host App")
app.include_router(router, prefix="/api/v1/chatbot")


@app.on_event("startup")
async def init_chatbot():
    await startup_chatbot()


@app.on_event("shutdown")
async def cleanup_chatbot():
    await shutdown_chatbot()


@app.get("/")
async def root():
    return {"message": "Host app running", "chatbot": "/api/v1/chatbot/health"}