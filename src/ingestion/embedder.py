# src/ingestion/embedder.py
import hashlib
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec
from config.settings import get_settings

settings = get_settings()


def _make_vector_id(pdf_path: str, chunk_index: int, chunk_text: str) -> str:
    """
    Generate a stable, idempotent ID for each chunk.
    
    WHY: Your notebook had no IDs — Pinecone auto-generated UUIDs.
    Re-ingesting the same PDF created DUPLICATE vectors.
    
    Now: same PDF + same chunk position = same ID → Pinecone upsert
    overwrites instead of duplicating. This is idempotency.
    """
    content = f"{pdf_path}::{chunk_index}::{chunk_text[:100]}"
    return hashlib.md5(content.encode()).hexdigest()


def get_or_create_index(pc: Pinecone):
    """Your notebook's index creation logic — unchanged logic, extracted."""
    if not pc.has_index(name=settings.pinecone_index_name):
        pc.create_index(
            name=settings.pinecone_index_name,
            dimension=settings.pinecone_dimension,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=settings.pinecone_cloud,
                region=settings.pinecone_region
            )
        )
    return pc.Index(settings.pinecone_index_name)


def embed_and_upsert(
    chunks: list[Document],
    pdf_path: str,
    batch_size: int = 100
) -> int:
    """
    Embed chunks and upsert to Pinecone with:
    - Idempotent hash IDs (prevents duplicates on re-run)
    - Batched upserts (prevents 429 rate limits)
    - Metadata stored per vector (enables filtered search later)
    
    Returns: number of vectors upserted
    """
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = get_or_create_index(pc)
    embedding_model = OpenAIEmbeddings(api_key=settings.openai_api_key)

    vectors = []
    for i, chunk in enumerate(chunks):
        vector_id = _make_vector_id(pdf_path, i, chunk.page_content)
        embedding = embedding_model.embed_query(chunk.page_content)

        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "text": chunk.page_content,
                "pdf_path": pdf_path,
                "chunk_index": i,
                # Add document metadata if available
                "page": chunk.metadata.get("page", 0),
            }
        })

    # Batch upserts to avoid Pinecone rate limits
    upserted = 0
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(vectors=batch)
        upserted += len(batch)
        print(f"[embedder] Upserted batch {i // batch_size + 1}: {len(batch)} vectors")

    return upserted