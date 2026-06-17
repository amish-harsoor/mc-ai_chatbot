import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.vector_stores.postgres import PGVectorStore
from src.config import configure_llama_index
import psycopg2

load_dotenv()

# Apply global LLM + embedding settings before doing anything else
configure_llama_index()

def ingest_documents_to_supabase():
    """
    Ingests documents to Supabase database for vector storage.
    This mirrors the local ingest.py but uses Supabase credentials.
    """
    
    # Check if all required Supabase credentials are present
    required_vars = ["SUPABASE_HOST", "SUPABASE_PORT", "SUPABASE_DATABASE", "SUPABASE_USER", "SUPABASE_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required Supabase environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file and ensure all Supabase credentials are set.")
        return False
    
    print("Loading documents from data/ folder...")
    
    # Check if data directory exists
    if not os.path.exists("data"):
        print("Error: 'data' directory not found. Please create it and add your documents.")
        return False
    
    # Read PDFs from the data directory
    try:
        documents = SimpleDirectoryReader("data/", recursive=True).load_data()
        print(f"Loaded {len(documents)} documents")
    except Exception as e:
        print(f"Error loading documents: {e}")
        return False

    if len(documents) == 0:
        print("Warning: No documents found in the data/ directory.")
        return False

    print("Chunking, embedding, and storing documents in Supabase PostgreSQL... (this may take a while)")
    
    try:
        # Create PGVectorStore for Supabase
        vector_store = PGVectorStore.from_params(
            host=os.getenv("SUPABASE_HOST"),
            port=int(os.getenv("SUPABASE_PORT", "5432")),
            database=os.getenv("SUPABASE_DATABASE", "postgres"),
            user=os.getenv("SUPABASE_USER"),
            password=os.getenv("SUPABASE_PASSWORD"),
            table_name="data_data_vectors",
            embed_dim=384,
        )
        
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        # Create the index from document chunks
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True,
        )

        print("Ingestion complete! Your documents are now searchable in Supabase PostgreSQL.")
        print(f"Successfully indexed {len(documents)} documents")
        
        # Verify the data was stored
        print("\nVerifying data storage...")
        conn = psycopg2.connect(
            host=os.getenv("SUPABASE_HOST"),
            port=int(os.getenv("SUPABASE_PORT", "5432")),
            database=os.getenv("SUPABASE_DATABASE", "postgres"),
            user=os.getenv("SUPABASE_USER"),
            password=os.getenv("SUPABASE_PASSWORD")
        )
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM data_data_vectors")
        count = cur.fetchone()[0]
        print(f"Verification: Found {count} vector records in Supabase database")
        
        cur.close()
        conn.close()
        
        return index
        
    except Exception as e:
        print(f"Error during ingestion to Supabase: {e}")
        return False

if __name__ == "__main__":
    ingest_documents_to_supabase()
