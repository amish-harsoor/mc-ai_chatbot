import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

def setup_supabase_database():
    """
    Sets up the Supabase database with pgvector extension and creates the necessary schema.
    This mirrors the local database setup for the chatbot application.
    """
    
    # Supabase connection parameters
    supabase_params = {
        "host": os.getenv("SUPABASE_HOST"),
        "port": os.getenv("SUPABASE_PORT", "5432"),
        "database": os.getenv("SUPABASE_DATABASE", "postgres"),
        "user": os.getenv("SUPABASE_USER"),
        "password": os.getenv("SUPABASE_PASSWORD", "")
    }
    
    # Check if all required Supabase credentials are present
    if not all([supabase_params["host"], supabase_params["user"]]):
        print("Error: Missing Supabase credentials. Please check your .env file.")
        print("Required: SUPABASE_HOST, SUPABASE_USER")
        return False
    
    if not supabase_params["password"]:
        print("Warning: SUPABASE_PASSWORD is empty. Please set it in your .env file.")
        return False
    
    try:
        print(f"Connecting to Supabase database at {supabase_params['host']}...")
        print(f"Using user: {supabase_params['user']}")
        print(f"Using database: {supabase_params['database']}")
        print(f"Using port: {supabase_params['port']}")
        
        # Create connection string
        connection_string = f"postgresql://{supabase_params['user']}:{supabase_params['password']}@{supabase_params['host']}:{supabase_params['port']}/{supabase_params['database']}"
        print(f"Connection string: postgresql://{supabase_params['user']}:[REDACTED]@{supabase_params['host']}:{supabase_params['port']}/{supabase_params['database']}")
        
        # Connect to Supabase database
        conn = psycopg2.connect(connection_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Enable pgvector extension (required for vector operations)
        print("Enabling pgvector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("pgvector extension enabled successfully.")
        
        # Create the data_vectors table if it doesn't exist
        print("Creating data_vectors table for vector storage...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS data_vectors (
                id SERIAL PRIMARY KEY,
                text_content TEXT NOT NULL,
                metadata JSONB,
                embedding vector(384) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("data_vectors table created successfully.")
        
        # Create indexes for better performance
        print("Creating indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_data_vectors_embedding 
            ON data_vectors 
            USING ivfflat (embedding vector_cosine_ops)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_data_vectors_created_at 
            ON data_vectors (created_at)
        """)
        print("Indexes created successfully.")
        
        # Grant necessary permissions (if needed)
        print("Setting up permissions...")
        cur.execute(f"""
            GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO CURRENT_USER
        """)
        cur.execute(f"""
            GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO CURRENT_USER
        """)
        print("Permissions set successfully.")
        
        # Verify setup
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'data_vectors'")
        if cur.fetchone():
            print("Verification successful: data_vectors table exists")
        else:
            print("Verification failed: data_vectors table not found")
            return False
            
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        if cur.fetchone():
            print("Verification successful: pgvector extension is enabled")
        else:
            print("Verification failed: pgvector extension not found")
            return False
        
        cur.close()
        conn.close()
        
        print("\nSupabase database setup completed successfully!")
        print("Your Supabase database is now ready for vector storage operations.")
        print("\nNext steps:")
        print("1. Run the ingest script to populate the database with documents")
        print("2. Update your application to use Supabase credentials when needed")
        
        return True
        
    except Exception as e:
        print(f"Error setting up Supabase database: {e}")
        return False

if __name__ == "__main__":
    setup_supabase_database()
