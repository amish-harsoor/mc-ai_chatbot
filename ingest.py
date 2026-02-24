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

    print("Chunking, embedding, and storing documents locally... (this may take a while)")
    # Create the index from document chunks
    index = VectorStoreIndex.from_documents(
        documents,
        show_progress=True,
    )

    # Persist the index to the 'storage' directory
    print("Saving index to ./storage...")
    index.storage_context.persist(persist_dir="./storage")

    print("Ingestion complete! Your documents are now searchable locally.")
    return index

if __name__ == "__main__":
    ingest_documents()