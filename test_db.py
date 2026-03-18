import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "mc_chatbot"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
    )
    print("Database connection successful!")
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM data_vectors;")
    count = cursor.fetchone()[0]
    print(f"Number of vectors in 'data_vectors' table: {count}")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Database operation failed: {e}")
