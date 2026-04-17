# config/settings.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Keys — loaded from .env or AWS Secrets Manager
    openai_api_key: str
    pinecone_api_key: str
    cohere_api_key: str

    # Pinecone config — matches your notebook
    pinecone_index_name: str = "legal-lense-index1"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    pinecone_dimension: int = 1536

    # Chunking config — your notebook values, now overridable
    chunk_size: int = 700
    chunk_overlap: int = 120

    # Retrieval config — your notebook values
    bm25_top_k: int = 10
    vector_top_k: int = 10
    rerank_top_n: int = 3
    bm25_weight: float = 0.4
    vector_weight: float = 0.6

    # LLM config
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1000

    # Circuit breaker config (Hour 2 concept)
    cohere_timeout_seconds: float = 5.0
    cohere_failure_threshold: int = 3   # open circuit after 3 failures

    # Storage (local dev — overridden to S3 in production)
    bm25_index_path: str = "data/raw/bm25_index.pkl"

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()