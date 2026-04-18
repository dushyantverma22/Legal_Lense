# tests/conftest.py
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from langchain_core.documents import Document


# ── Sample data fixtures ────────────────────────────────────────────────────

@pytest.fixture
def sample_docs():
    """Minimal LangChain Documents — exactly what load_pdf_smart() returns."""
    return [
        Document(
            page_content="This Rent Agreement is made at Gurugram on 05/01/2026 between "
                         "Smti. Suresh Devi and Mr. Dushyant Kumar Verma.",
            metadata={"page": 0}
        ),
        Document(
            page_content="The Lessee shall pay rent of Rs. 17,600/- every month before "
                         "07th day of each English calendar month to the owner.",
            metadata={"page": 1}
        ),
        Document(
            page_content="The Tenancy shall commence from 01/10/2025 to 31/08/2026 "
                         "for 11 months. Lock-in period is 11 months.",
            metadata={"page": 2}
        ),
    ]


@pytest.fixture
def sample_chunks(sample_docs):
    """
    Pre-chunked documents — skip the actual splitter for unit tests
    that don't care about chunking logic itself.
    """
    from src.ingestion.chunker import chunk_documents
    return chunk_documents(sample_docs)


@pytest.fixture
def sample_pdf_path(tmp_path):
    """
    Creates a real (tiny) PDF file in a temp directory.
    Used by integration tests that need an actual file path.
    """
    # Write a minimal text file that acts as a PDF placeholder
    # In real tests you'd use a tiny test PDF committed to the repo
    pdf_file = tmp_path / "test_agreement.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 minimal test fixture")
    return str(pdf_file)


# ── Mock fixtures for external APIs ────────────────────────────────────────

@pytest.fixture
def mock_openai():
    """
    Mocks the OpenAI client so no real API calls are made.
    Returns a fake completion response that looks exactly like
    what gpt-4o-mini returns.
    
    WHY MOCK: unit + integration tests must not call OpenAI.
    - Costs money per call
    - Introduces network flakiness
    - Makes tests non-deterministic (LLM output varies)
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        "The rent amount is Rs. 17,600/- per month, due before the 7th."
    )
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 412
    mock_response.usage.completion_tokens = 24

    with patch("openai.OpenAI") as mock_client_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_pinecone():
    """
    Mocks Pinecone so no real index calls happen.
    Returns fake similarity search results using sample text.
    """
    fake_results = [
        (
            Document(page_content="The Lessee shall pay rent of Rs. 17,600/-"),
            0.92,   # cosine similarity score
        ),
        (
            Document(page_content="Tenancy commences 01/10/2025 for 11 months"),
            0.78,
        ),
    ]

    with patch("langchain_pinecone.PineconeVectorStore") as mock_vs_class:
        mock_vs = MagicMock()
        mock_vs.similarity_search_with_score.return_value = fake_results
        mock_vs.as_retriever.return_value = MagicMock()
        mock_vs_class.return_value = mock_vs
        yield mock_vs


@pytest.fixture
def mock_cohere():
    """
    Mocks Cohere reranking — returns docs in original order.
    """
    mock_result = MagicMock()
    mock_result.results = [
        MagicMock(index=0, relevance_score=0.95),
        MagicMock(index=1, relevance_score=0.82),
    ]

    with patch("cohere.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.rerank.return_value = mock_result
        mock_client_class.return_value = mock_client
        yield mock_client


# ── FastAPI TestClient fixture ──────────────────────────────────────────────

@pytest.fixture
def api_client(mock_pinecone, mock_openai, mock_cohere, sample_chunks):
    """
    Creates a FastAPI TestClient with a fully initialised app.
    Pre-loads sample_chunks so /query works without real ingestion.
    
    This is the fixture used by ALL api/ tests.
    It patches startup so no real Pinecone connection is made.
    """
    from src.api.main import app
    from src.api import dependencies

    # Pre-populate the in-memory chunk store
    dependencies._chunks = list(sample_chunks)

    # Patch the vectorstore singleton with the mock
    dependencies._vectorstore = mock_pinecone

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    # Cleanup after test
    dependencies._chunks = []
    dependencies._vectorstore = None