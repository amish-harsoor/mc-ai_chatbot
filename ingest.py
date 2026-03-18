import os
from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.vector_stores.postgres import PGVectorStore
from config import configure_llama_index
import psycopg2

load_dotenv()

# Apply global LLM + embedding settings before doing anything else
configure_llama_index()

def ingest_documents():
    print("Loading documents from data/ folder...")
    # Read PDFs from the data directory
    documents = SimpleDirectoryReader("data/", recursive=True).load_data()
    print(f"Loaded {len(documents)} documents")

    print("Chunking, embedding, and storing documents in PostgreSQL... (this may take a while)")
    
    # Create PGVectorStore
    vector_store = PGVectorStore.from_params(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "mc_chatbot"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        table_name="data_vectors",
        embed_dim=384,
    )
    
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    # Create the index from document chunks
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )

    print("Ingestion complete! Your documents are now searchable in PostgreSQL.")
    return index

if __name__ == "__main__":
    ingest_documents()