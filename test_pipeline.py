# test_pipeline.py  (run from project root: python test_pipeline.py)
import sys
sys.path.insert(0, ".")

from src.ingestion.loader import load_pdf_smart
from src.ingestion.chunker import chunk_documents
from src.ingestion.embedder import embed_and_upsert
from src.generation.chain import run_rag_query, get_vectorstore
from config.settings import get_settings

settings = get_settings()

# Use your actual PDF path
PDF_PATH = "data//sample_rent.pdf"

print("=== INGESTION PIPELINE ===")
docs = load_pdf_smart(PDF_PATH)
print(f"Loaded {len(docs)} documents")

chunks = chunk_documents(docs)
print(f"Created {len(chunks)} chunks")

upserted = embed_and_upsert(chunks, PDF_PATH)
print(f"Upserted {upserted} vectors (idempotent — re-run safely)")

print("\n=== QUERY PIPELINE ===")
vectorstore = get_vectorstore()

question = "What is the rent amount and due date mentioned in the lease agreement?"
result = run_rag_query(question, chunks, vectorstore)

print(f"Answer: {result['answer']}")
print(f"Reranked: {result['reranked']}")
print(f"Chunks used: {result['chunk_count']}")
print(f"Sources preview: {result['sources'][0][:100]}...")