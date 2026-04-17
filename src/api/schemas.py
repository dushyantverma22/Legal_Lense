# src/api/schemas.py
from pydantic import BaseModel, Field
from typing import Optional
import uuid


class IngestRequest(BaseModel):
    """
    What callers send to POST /ingest when not uploading a file directly.
    For file uploads we use FastAPI's UploadFile instead.
    """
    pdf_path: str = Field(..., description="Path to the PDF on disk or S3 URI")
    namespace: Optional[str] = Field(None, description="Pinecone namespace for multi-tenant isolation")


class IngestResponse(BaseModel):
    """
    Returned immediately — ingestion runs in the background.
    202 Accepted pattern: caller gets a job_id to poll status.
    """
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "accepted"
    message: str
    pdf_path: str


class QueryRequest(BaseModel):
    """
    What callers send to POST /query.
    Mirrors your notebook's question variable exactly.
    """
    question: str = Field(..., min_length=3, max_length=1000)
    top_k: Optional[int] = Field(None, ge=1, le=20, description="Override default retrieval k")
    namespace: Optional[str] = Field(None, description="Pinecone namespace to query")


class QueryResponse(BaseModel):
    """
    Structured response — much richer than your notebook's raw string.
    Every field here is something you'll want to log and monitor.
    """
    answer: str
    sources: list[str]
    chunk_count: int
    reranked: bool
    latency_ms: float
    request_id: str


class HealthResponse(BaseModel):
    status: str
    pinecone_connected: bool
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    """Consistent error shape — never return raw Python tracebacks."""
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None