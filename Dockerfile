# API service only. The React widget in frontend/ChatbotUI is hosted separately.
FROM python:3.11-slim

WORKDIR /app

# libgomp1: OpenMP runtime used by CPU torch / sentence-transformers on slim.
# psycopg2-binary ships its own libpq; gcc/libpq-dev are not required.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

# CPU torch first so huggingface embeddings + SentenceTransformer rerank
# do not pull CUDA wheels from PyPI.
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir -r requirements.txt

# Catalog JSON under data/ is gitignored; it must be present at build time
# (or bind-mount /app/data at run time). Ingest uploads also write here.
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser data ./data

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/appuser/.cache/huggingface

USER appuser

EXPOSE 8000

# Startup loads embedding + rerank models; first boot can be slow if they
# are not already in the HuggingFace cache.
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
