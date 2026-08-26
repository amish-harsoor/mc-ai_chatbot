# MC AI Chatbot

A **RAG-powered course advisor** for Management Concepts. It answers questions about courses using a PostgreSQL/pgvector knowledge base and streams responses over a simple HTTP API.

Use it in three ways:

1. **Standalone microservice** — deploy on its own; any app calls it over HTTP *(recommended)*
2. **Mounted FastAPI router** — embed routes inside an existing FastAPI app
3. **React widget** — drop-in chat UI that talks to the API

---

## Integration at a glance

| Your app | Recommended approach | Effort |
|----------|---------------------|--------|
| FastAPI, Django, Node, etc. | Call the service over HTTP with `ChatbotClient` or `fetch` | Low |
| Existing FastAPI app | Mount `router` + call `startup_chatbot()` | Medium |
| Website / LMS | Use the React widget + point `VITE_API_BASE_URL` at the API | Low |

```text
┌─────────────────────┐         HTTP          ┌──────────────────────┐
│  Your app           │  ──────────────────►  │  MC AI Chatbot       │
│  (FastAPI / Django) │  /session/start       │  (FastAPI service)   │
│                     │  /chat/stream         │                      │
│  Optional: React    │  /session/.../history └──────────┬───────────┘
│  widget             │                                    │
└─────────────────────┘                                    ▼
                                                  ┌──────────────────────┐
                                                  │  Postgres + pgvector │
                                                  └──────────────────────┘
```

---

## Quick start (standalone service)

### 1. Environment variables

Create a `.env` file in the project root:

```env
# Chat LLM — OpenAI is primary; OpenRouter/Groq are config-time fallbacks
OPENAI_API_KEY=your_openai_key_here
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
LLM_FALLBACK_PROVIDERS=openrouter,groq
# Fallbacks (optional but recommended)
OPENROUTER_API_KEY=your_openrouter_key
GROQ_API_KEY=your_groq_key

# Database — local Postgres (code defaults USE_SUPABASE=true)
USE_SUPABASE=false
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=coursebot

# Or Supabase (see src/db/vector_config.py)
# USE_SUPABASE=true
# SUPABASE_HOST=...
```

### 2. Run with Docker

Catalog JSON under `data/` is gitignored and is copied into the image at build time. Put `data/management_concepts_courses.json` (and optionally `data/course_prices.json`) on the machine that runs `docker build`, or bind-mount `data/` at run time.

`DB_HOST=localhost` inside the container is the container itself. For Postgres on the host, use `host.docker.internal` (Docker Desktop) or the Compose service name.

```bash
docker build -t mc-ai-chatbot .
docker run -p 8000:8000 --env-file .env -e DB_HOST=host.docker.internal mc-ai-chatbot
```

### 3. Run locally (no Docker)

```bash
pip install -r requirements.txt
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### 4. Verify it works

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl -X POST http://localhost:8000/session/start
# {"session_id":"<uuid>"}
```

Interactive API docs: **http://localhost:8000/docs**

---

## Integrating with other apps

### Option A — HTTP microservice (recommended)

Run the chatbot as its own service. Your host app never imports LlamaIndex or embedding models — it just makes HTTP calls.

**Python (any framework)** — use the built-in client:

```python
from src.client import ChatbotClient

client = ChatbotClient(
    "http://localhost:8000",
    api_key="your-secret",          # optional, if CHATBOT_API_KEY is set
    prefix="/api/v1/chatbot",       # optional, if CHATBOT_API_PREFIX is set
)

# 1. Start a session when the user opens chat
session = client.start_session()
session_id = session["session_id"]

# 2. Stream a response
for chunk in client.chat_stream(session_id, "Recommend project management courses"):
    print(chunk, end="", flush=True)

# 3. Load history (e.g. on page reload)
history = client.get_history(session_id)
```

**FastAPI BFF** — proxy through your app so the browser only talks to one origin:

```python
import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()
CHATBOT = "http://chatbot-service:8000"

@app.post("/api/chat/stream")
async def chat(body: dict):
    async with httpx.AsyncClient() as client:
        req = client.build_request("POST", f"{CHATBOT}/chat/stream", json=body)
        resp = await client.send(req, stream=True)

        async def forward():
            async for chunk in resp.aiter_text():
                yield chunk

        return StreamingResponse(forward(), media_type="text/plain")
```

**curl / JavaScript / any language** — same JSON contract:

```bash
# Start session
curl -X POST http://localhost:8000/session/start

# Chat (streaming)
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<uuid>","message":"What budgeting courses do you offer?"}'
```

```javascript
const res = await fetch("http://localhost:8000/chat/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ session_id, message: "Hello" }),
});
const reader = res.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  console.log(decoder.decode(value));
}
```

---

### Option B — Mount into an existing FastAPI app

Import the router and wire up startup/shutdown. Full working example: [`examples/fastapi_mount.py`](examples/fastapi_mount.py).

```python
from fastapi import FastAPI
from src.api.router import router
from src.api.app import startup_chatbot, shutdown_chatbot

app = FastAPI(title="My Host App")
app.include_router(router, prefix="/api/v1/chatbot")

@app.on_event("startup")
async def init_chatbot():
    await startup_chatbot()

@app.on_event("shutdown")
async def cleanup_chatbot():
    await shutdown_chatbot()
```

Routes are then available at `/api/v1/chatbot/health`, `/api/v1/chatbot/chat/stream`, etc.

Or use the app factory for a self-contained chatbot app:

```python
from src.api import create_app

app = create_app(prefix="/api/v1/chatbot")
```

---

### Option C — Django

Django cannot mount FastAPI routers directly. Proxy requests to the chatbot service instead.

Full example view: [`examples/django_proxy.py`](examples/django_proxy.py).

```python
# urls.py
from django.urls import path
from examples.django_proxy import chat_stream_proxy

urlpatterns = [
    path("api/chat/stream/", chat_stream_proxy),
]
```

Set in Django's environment:

```env
CHATBOT_SERVICE_URL=http://localhost:8000
CHATBOT_API_PREFIX=          # leave empty unless you set CHATBOT_API_PREFIX on the service
CHATBOT_API_KEY=your-secret  # optional
```

For other endpoints (`/session/start`, `/history`), add similar proxy views or call `ChatbotClient` from Django views.

---

### Option D — React chat widget

The widget lives in `frontend/ChatbotUI/`.

```bash
cd frontend/ChatbotUI
npm install
```

Create `frontend/ChatbotUI/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

If the API is behind a prefix or BFF, include the full base:

```env
VITE_API_BASE_URL=http://localhost:9000/api/v1/chatbot
```

```bash
npm run dev      # development
npm run build    # production bundle in dist/
```

The widget calls `/session/start`, `/chat/stream`, and `/session/{id}/history` on that base URL.

---

## API reference

All paths below are relative to the service root. If `CHATBOT_API_PREFIX=/api/v1/chatbot` is set, prepend that prefix (e.g. `/api/v1/chatbot/health`).

| Method | Path | Single responsibility |
|--------|------|----------------------|
| `GET` | `/health` | Liveness check (no auth) |
| `POST` | `/session/start` | Create a chat session (returns owner + optional profile snapshot) |
| `POST` | `/chat/stream` | Generate a bot reply and stream it (`text/plain`) |
| `GET` | `/session/{session_id}/history` | Load full message history for one session |
| `POST` | `/session/{session_id}/message` | Persist one message **without** a bot reply (onboarding UI) |
| `GET` | `/learner/{owner_id}/profile` | Read durable learner profile |
| `GET` | `/learner/{owner_id}/sessions` | List session snapshots for an owner |
| `POST` | `/ingest` | Ingest **one** file **or** URL into the vector store |

### Identity (guest vs registered)

Every session and message can include:

- `user_id` — registered host-app user (preferred when present)
- `guest_id` — stable anonymous id (widget stores `localStorage.mc_guest_id`)

All user/assistant turns are always written to `chat_messages` (full text for history and future recommendation work). Condensed prefs/stats are updated on `chat_sessions` + `learner_profiles` automatically (not opt-in).

### `POST /session/start` body

```json
{ "guest_id": "guest_…", "user_id": null }
```

Response includes `session_id`, `owner_id`, `owner_type`, and optional durable `profile`.

### `POST /chat/stream` body

```json
{
  "session_id": "uuid-from-session-start",
  "message": "Recommend courses for a new project manager",
  "display_message": "Optional UI-friendly version of the user message",
  "silent_response": false,
  "guest_id": "guest_…",
  "metadata": {
    "step": "goal",
    "profile_complete": true,
    "profile": {
      "experience": "Entry-level",
      "department": "Finance",
      "goal": "Get a promotion"
    }
  }
}
```

- `display_message` — stored in history for the UI; LLM still sees `message`
- `silent_response` — if `true`, assistant reply is saved but marked not visible in history
- `metadata` — profile / support context for routing and prefs
- `guest_id` / `user_id` — owner identity for session + profile tracking

This endpoint always produces a reply (support, out-of-domain, or RAG). To save onboarding selections without a reply, use `POST /session/{id}/message`.

### `POST /session/{session_id}/message` body

```json
{
  "role": "assistant",
  "content": "Welcome! What is your experience level?",
  "display_content": "Welcome!",
  "metadata": { "step": "welcome", "type": "onboarding" },
  "guest_id": "guest_…"
}
```

### `POST /ingest`

File (multipart):

```bash
curl -X POST http://localhost:8000/ingest -F "file=@data/my-course.pdf"
```

URL (JSON):

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/courses", "force": false}'
```

---

## Configuration

### Service / integration

| Variable | Default | Description |
|----------|---------|-------------|
| `CHATBOT_API_PREFIX` | *(empty)* | URL prefix for all routes, e.g. `/api/v1/chatbot` |
| `CHATBOT_API_KEY` | *(empty)* | If set, clients must send `X-API-Key` header (except `/health`) |
| `API_PREFIX` | *(empty)* | Alias for `CHATBOT_API_PREFIX` |
| `API_KEY` | *(empty)* | Alias for `CHATBOT_API_KEY` |

### LLM (chat only — not embeddings)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | Primary chat provider: `openai`, `openrouter`, `groq`, or `auto` |
| `OPENAI_API_KEY` | — | Preferred key for free-chat / RAG answers |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI chat model id |
| `OPENAI_API_BASE` | — | Optional custom OpenAI-compatible base URL |
| `LLM_FALLBACK_PROVIDERS` | `openrouter,groq` | Tried in order if primary fails to configure |
| `OPENROUTER_API_KEY` | — | Fallback when OpenAI is unavailable |
| `OPENROUTER_MODEL` | `meta-llama/llama-3.2-3b-instruct:free` | OpenRouter model id |
| `GROQ_API_KEY` | — | Second fallback |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model id |

### Embeddings

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBED_PROVIDER` | `huggingface` | `huggingface`, `fastembed`, `openrouter`, or `openai` |
| `EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model name |

### Database

| Variable | Description |
|----------|-------------|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | Local Postgres |
| `USE_SUPABASE` | Set `true` to use Supabase connection vars (see `src/db/vector_config.py`) |

### Chat behaviour

| Variable | Default | Description |
|----------|---------|-------------|
| `CHAT_MEMORY_TOKEN_LIMIT` | `3000` | Max tokens in chat memory |
| `SESSION_ENGINE_TTL_SECONDS` | `1800` | Session engine cache TTL |
| `SESSION_ENGINE_CACHE_MAX_SIZE` | `200` | Max cached session engines |

---

## Install as a Python package

```bash
pip install -e .
```

Exports:

```python
from src.api import create_app, router, startup_chatbot, shutdown_chatbot
from src.client import ChatbotClient
```

---

## Project structure

```text
mc-ai_chatbot/
├── Dockerfile
├── pyproject.toml              # pip-installable package
├── requirements.txt
├── examples/
│   ├── fastapi_mount.py        # mount router in another FastAPI app
│   └── django_proxy.py         # Django streaming proxy example
├── frontend/ChatbotUI/         # React chat widget
└── src/
    ├── api/
    │   ├── main.py             # standalone entry: uvicorn src.api.main:app
    │   ├── app.py              # create_app(), startup/shutdown helpers
    │   ├── router/             # APIRouter package — mount into host apps
    │   │   ├── __init__.py     # aggregates domain routers
    │   │   ├── deps.py         # shared request helpers
    │   │   ├── health.py       # GET /health
    │   │   ├── sessions.py     # session start / history / save message
    │   │   ├── chat.py         # POST /chat/stream
    │   │   ├── ingest.py       # POST /ingest (file or URL)
    │   │   └── learners.py     # learner profile & session list
    │   ├── schemas.py          # Pydantic request/response models
    │   └── settings.py         # API prefix & key config
    ├── client.py               # ChatbotClient HTTP SDK
    ├── chatbot/                # RAG engine, retrieval, chat logic
    ├── db/                     # Postgres session store, vector config
    ├── ingestion/              # Document ingestion pipeline
    └── config.py               # LLM & embedding configuration
```

---

## Data ingestion

To update the knowledge base:

1. Place PDFs or text files in `data/`
2. Ensure Postgres/Supabase is running
3. Run ingestion:

```bash
# Local Postgres
python src/ingestion/ingest.py

# Supabase
python src/ingestion/ingest.py --supabase
```

Or ingest at runtime via the API:

```bash
curl -X POST http://localhost:8000/ingest -F "file=@data/my-course.pdf"

curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/courses", "force": false}'
```

---

## Development

```bash
pip install -r requirements.txt
pytest tests/ -q
```

Key modules for contributors:

- `src/chatbot/chatbot.py` — chat engine, session cache, `get_index()`
- `src/chatbot/retrieval.py` — hybrid search + reranking
- `src/ingestion/pipeline.py` — chunking, dedup, vector upsert

---

## Architecture

| Layer | Technology |
|-------|------------|
| API | FastAPI |
| RAG | LlamaIndex |
| Vector DB | PostgreSQL + pgvector (or Supabase) |
| Embeddings | `all-MiniLM-L6-v2` locally by default (no API key) |
| LLM | Groq or OpenRouter (configurable) |
| Frontend | React + Vite widget |

---

## Typical integration checklist

- [ ] Deploy chatbot service (Docker or uvicorn) with `.env` configured
- [ ] Confirm `GET /health` returns `{"status":"ok"}`
- [ ] In host app: `POST /session/start` when user opens chat
- [ ] Stream replies via `POST /chat/stream` with the `session_id`
- [ ] On reload: `GET /session/{id}/history` to restore the thread
- [ ] (Optional) Set `CHATBOT_API_KEY` and pass `X-API-Key` from your BFF
- [ ] (Optional) Point React widget `VITE_API_BASE_URL` at service or BFF
- [ ] (Optional) Mount `router` in FastAPI if you want in-process routes