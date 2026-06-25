import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

import psycopg2
from src.db.vector_config import get_db_params, get_vector_table_name

conn = psycopg2.connect(**get_db_params())
cur = conn.cursor()
cur.execute(
    """
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public'
      AND (table_name LIKE '%vector%' OR table_name LIKE 'data%')
    ORDER BY table_name
    """
)
print("configured:", get_vector_table_name())
for (table,) in cur.fetchall():
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"  {table}: {cur.fetchone()[0]}")
conn.close()