# src/api/dependencies.py
from functools import lru_cache
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone
from langchain_core.documents import Document
from config.settings import get_settings

settings = get_settings()

# Module-level singletons — created once on app startup
_vectorstore: PineconeVectorStore | None = None
_chunks: list[Document] = []


def init_vectorstore() -> PineconeVectorStore:
    global _vectorstore

    embedding_model = OpenAIEmbeddings(api_key=settings.openai_api_key)

    _vectorstore = PineconeVectorStore(
        index_name=settings.pinecone_index_name,
        embedding=embedding_model,
        pinecone_api_key=settings.pinecone_api_key   # ✅ FIX
    )

    print(f"[deps] Pinecone vectorstore initialised: {settings.pinecone_index_name}")
    return _vectorstore


def get_vectorstore() -> PineconeVectorStore:
    """
    FastAPI dependency — injected into route handlers.
    Returns the already-initialised vectorstore.
    Raises clearly if startup didn't run.
    """
    if _vectorstore is None:
        raise RuntimeError("Vectorstore not initialised. Did app startup run?")
    return _vectorstore


def get_chunks() -> list[Document]:
    """
    Returns in-memory chunks for BM25.
    
    NOTE: In production this becomes a Redis/S3 load.
    For now it's the in-memory list populated at ingest time.
    This is the one piece of state that Hour 4 will replace
    with a proper persistent store.
    """
    return _chunks


def add_chunks(new_chunks: list[Document]) -> None:
    """Called by the ingestion background task to register new chunks."""
    global _chunks
    _chunks.extend(new_chunks)
    print(f"[deps] Chunk store now has {len(_chunks)} chunks total")