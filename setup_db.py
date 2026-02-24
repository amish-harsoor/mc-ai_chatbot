import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

def setup_database():
    # Connection parameters for the default 'postgres' database
    db_params = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
        "port": os.getenv("DB_PORT", "5432")
    }
    
    # Database to create
    target_db = os.getenv("DB_NAME", "mc_chatbot")
    
    try:
        # Connect to default postgres DB to create the new one
        print(f"Connecting to database 'postgres' as user '{db_params['user']}'...")
        conn = psycopg2.connect(**db_params, database="postgres")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
        exists = cur.fetchone()
        
        if not exists:
            print(f"Creating database {target_db}...")
            cur.execute(f'CREATE DATABASE "{target_db}"')
            print(f"Database {target_db} created successfully.")
        else:
            print(f"Database {target_db} already exists.")
            
        cur.close()
        conn.close()
        
        # Connect to the new database to enable pgvector extension
        print(f"Connecting to database '{target_db}' to enable extensions...")
        conn = psycopg2.connect(**db_params, database=target_db)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        print("Enabling pgvector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("Extension 'vector' enabled.")
        
        cur.close()
        conn.close()
        
        return True
    except Exception as e:
        print(f"Error setting up database: {e}")
        return False

if __name__ == "__main__":
    setup_database()
