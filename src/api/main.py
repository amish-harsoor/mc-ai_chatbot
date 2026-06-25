# --- Import path fix (supports direct execution) ---
# This allows running the file directly without PYTHONPATH:
#   python src/api/main.py
#   (Docker uses ENV PYTHONPATH=/app instead)
import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
# --- end import path fix ---

import logging

from src.api.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000)