# MC AI Chatbot

An AI-powered course assistant chatbot for the **Management Concepts (MC)** online learning platform. It answers student questions about courses, fees, schedules, instructors, and FAQs using a Retrieval-Augmented Generation (RAG) pipeline backed by a PostgreSQL vector store.

---

## Features

- **RAG-powered answers** — Retrieves relevant course content before generating responses, keeping answers grounded in real data.
- **Conversational memory** — Each user session maintains its own chat history (token-capped to prevent prompt bloat).
- **PostgreSQL + pgvector** — Embeddings are stored and queried directly in a Postgres database using the `pgvector` extension.
- **FastAPI backend** — Lightweight, async REST API with session management.
- **Plain HTML frontend** — A simple chat widget that communicates with the backend via `fetch`.
- **Local embeddings** — Uses `all-MiniLM-L6-v2` from HuggingFace (runs offline, no API key required for embeddings).
- **OpenRouter LLM** — Routes LLM calls to `meta-llama/llama-3.1-8b-instruct` (free tier) via OpenRouter.

---

## Project Structure

```
mc-ai_chatbot/
├── data/               # Place your course PDFs, text files, and documents here
├── config.py           # Global LlamaIndex settings (LLM, embeddings, chunking)
├── ingest.py           # One-time script to load, chunk, embed, and store documents
├── chatbot.py          # Loads the vector index and creates per-session chat engines
├── main.py             # FastAPI app with /session/start, /chat, and /health endpoints
├── index.html          # Minimal browser-based chat UI
├── .env                # API keys and database connection string (not committed)
├── .gitignore
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Llama 3.1 8B via [OpenRouter](https://openrouter.ai) |
| Embeddings | `all-MiniLM-L6-v2` (HuggingFace, 384-dim) |
| RAG Framework | [LlamaIndex](https://docs.llamaindex.ai) |
| Vector Store | PostgreSQL + `pgvector` |
| API Server | [FastAPI](https://fastapi.tiangolo.com) + Uvicorn |
| Frontend | HTML + Vanilla JavaScript |

---

## Quick Start (5-Step Process)

1. **Install Dependencies**: Run `pip install -r requirements.txt` (or install the packages listed in the Setup section).
2. **Initialize Database**: Create a PostgreSQL database and enable the vector extension: `CREATE EXTENSION vector;`.
3. **Add Data**: Place your course PDFs or text files into the `data/` folder.
4. **Run Ingestion**: Execute `python ingest.py` to chunk, embed, and store your documents.
5. **Start Application**: Run `uvicorn main:app --reload` and open `index.html` in your browser.

---

## Setup

### 1. Prerequisites

- Python 3.10+
- PostgreSQL with the [`pgvector`](https://github.com/pgvector/pgvector) extension installed
- An [OpenRouter](https://openrouter.ai) account and API key

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv llama-index llama-index-vector-stores-postgres llama-index-embeddings-huggingface llama-index-llms-openai-like psycopg2-binary
```

### 4. Set up the PostgreSQL database

Connect to Postgres and run:

```sql
CREATE DATABASE coursebot;
\c coursebot
CREATE EXTENSION vector;
```

### 5. Add your course documents

Place your PDFs, text files, or other course documents inside the `data/` folder:

```
data/
├── course_catalog.pdf
├── faq.txt
└── ...
```

### 6. Ingest documents (run once)

This step chunks, embeds, and stores your documents in the vector database:

```bash
python ingest.py
```

> You only need to re-run this when your course documents change.

### 7. Start the API server

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

### 8. Open the chat UI

Open `index.html` directly in your browser. It will automatically connect to the backend and start a session.

---

## API Reference

### `POST /session/start`

Creates a new chat session with fresh memory. Call this when a user opens the chat.

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### `POST /chat`

Sends a user message and returns the AI's answer.

**Request body:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "What courses do you offer in project management?"
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "answer": "We offer several project management courses including..."
}
```

---

### `GET /health`

Returns the health status and number of active sessions.

**Response:**
```json
{
  "status": "ok",
  "active_sessions": 3
}
```

---

## Configuration

All LLM and embedding settings are centralized in `config.py`:

| Setting | Value |
|---|---|
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Embedding dimensions | 384 |
| LLM | `meta-llama/llama-3.1-8b-instruct:free` |
| LLM temperature | 0.3 |
| Max tokens | 1024 |
| Chunk size | 512 tokens |
| Chunk overlap | 50 tokens |
| Retrieval top-k | 4 chunks |
| Chat memory limit | 3000 tokens |

---

## Notes

- **Session isolation**: Each call to `POST /session/start` creates an independent chat engine. Users cannot see each other's conversation history.
- **Re-ingestion**: Running `ingest.py` again will add documents to the existing table. If you want a clean slate, drop and recreate the `course_embeddings` table in Postgres first.
- **Switching LLMs**: Update the `model` and `api_base` parameters in `config.py`. Make sure to also update your `.env` with the appropriate API key.
- **Switching embedding models**: If you change the embedding model, you must also update `embed_dim` in both `ingest.py` and `chatbot.py`, and re-run `ingest.py` from scratch.

---

## License

This project is for internal use by the Management Concepts team.
