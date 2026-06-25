"""Deprecated: use `python src/db/init.py --supabase` instead."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.db.init import init_database

if __name__ == "__main__":
    os.environ["USE_SUPABASE"] = "true"
    init_database(configure_embeddings=True)