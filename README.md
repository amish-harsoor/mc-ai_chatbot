# MC AI Chatbot 

This repository contains the backend and simple frontend for the **Management Concepts (MC) AI Course Chatbot**. 

It uses Retrieval-Augmented Generation (RAG) to answer user questions about courses, grounded in data stored in a PostgreSQL database (or Supabase) using the `pgvector` extension.


---

## 🏗️ Architecture Stack

- **Framework:** FastAPI (Python)
- **RAG Engine:** LlamaIndex
- **Vector DB:** PostgreSQL + `pgvector` (or Supabase)
- **Embeddings:** `all-MiniLM-L6-v2` (runs locally, no API key needed)
- **LLM:** `meta-llama/llama-3.1-8b-instruct` (via OpenRouter/Groq)
- **Frontend:** Vanilla HTML/JS

---

## 🚀 Quick Start (Local Development)

The easiest way to run this locally is using **Docker**.

### 1. Environment Variables
Create a `.env` file in the root directory. You will need:
```env
OPENROUTER_API_KEY=your_key_here
# Or GROQ_API_KEY=your_key_here if using Groq
LLM_PROVIDER=openrouter # or groq

# If using local Postgres
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=coursebot

# If using Supabase, set USE_SUPABASE=true and configure Supabase vars
```

### 2. Build and Run with Docker
```bash
# Build the image
docker build -t mc-ai-chatbot .

# Run the container (injects your .env file)
docker run -p 8000:8000 --env-file .env mc-ai-chatbot
```
The API and Chat UI will now be available at: **http://localhost:8000**

---

## 📁 Project Structure

```text
mc-ai_chatbot/
├── Dockerfile              # Docker configuration
├── requirements.txt        # Python dependencies
├── index.html              # Simple Chat UI widget
├── src/
│   ├── api/main.py         # FastAPI application entrypoint
│   ├── chatbot/            # LlamaIndex query engines and chat logic
│   ├── db/                 # Database connection and setup scripts
│   ├── ingestion/          # Scripts to embed and store PDFs/text into Postgres
│   └── config.py           # Global settings for LLM and Embeddings
└── data/                   # (Not committed) Place raw PDFs/docs here for ingestion
```

---

## 📚 Data Ingestion

If you need to update the chatbot's knowledge base:
1. Place your new course PDFs or text files in the `data/` folder.
2. Ensure your Postgres/Supabase database is running and reachable.
3. Run the ingestion script to chunk, embed, and save to the database:
   ```bash
   # If running locally (without docker)
   python src/ingestion/ingest.py
   
   # Or for Supabase
   python src/ingestion/ingest_supabase.py
   ```

---

## 🔗 API Endpoints

- `POST /session/start` - Generates a new `session_id` to track chat history.
- `POST /chat/stream` - Send a message and get a streaming text response (Server-Sent Events style).
- `GET /health` - Check API status.

*(You can view the full interactive API docs by visiting `http://localhost:8000/docs` while the server is running).*
