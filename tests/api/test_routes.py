# tests/api/test_routes.py
import pytest
from unittest.mock import patch


def test_health_endpoint_returns_200(api_client):
    """Health check must always return 200 with status=ok."""
    response = api_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_status_endpoint_shows_chunk_count(api_client):
    """
    /status must report the chunk count loaded by the fixture.
    Confirms our dependency injection (get_chunks) wires correctly.
    """
    response = api_client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["chunks_in_memory"] > 0
    assert data["ready"] is True


def test_query_returns_200_with_valid_question(api_client):
    """
    POST /query with a valid question must return 200 and
    the full QueryResponse schema.
    
    This is the most important API test — it validates the
    entire chain from HTTP → pipeline → response.
    """
    response = api_client.post(
        "/api/v1/query",
        json={"question": "What is the monthly rent amount?"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "chunk_count" in data
    assert "reranked" in data
    assert "latency_ms" in data
    assert "request_id" in data

    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0
    assert isinstance(data["sources"], list)
    assert data["latency_ms"] > 0


def test_query_returns_request_id_header(api_client):
    """
    The X-Request-ID header must be present on every response.
    This confirms the middleware is wired correctly.
    """
    response = api_client.post(
        "/api/v1/query",
        json={"question": "Who are the parties in this agreement?"},
    )
    assert "x-request-id" in response.headers


def test_query_respects_custom_request_id(api_client):
    from unittest.mock import patch

    custom_id = "test-trace-abc123"

    with patch("src.api.routes.run_rag_query") as mock_rag:
        mock_rag.return_value = {
            "answer": "The deposit is $500.",
            "sources": ["sample chunk"],
            "chunk_count": 1,
            "reranked": False,
        }

        response = api_client.post(
            "/api/v1/query",
            json={"question": "What is the security deposit?"},
            headers={"X-Request-ID": custom_id},
        )

    assert response.headers.get("x-request-id") == custom_id
    assert response.json()["request_id"] == custom_id


def test_query_rejects_empty_question(api_client):
    """Pydantic validation: question shorter than 3 chars must return 422."""
    response = api_client.post(
        "/api/v1/query",
        json={"question": "hi"},  # too short: min_length=3
    )
    assert response.status_code == 422


def test_query_rejects_missing_question(api_client):
    """Missing required field must return 422, not 500."""
    response = api_client.post("/api/v1/query", json={})
    assert response.status_code == 422


def test_query_returns_200_with_valid_question(api_client):
    from unittest.mock import patch

    with patch("src.api.routes.run_rag_query") as mock_rag:
        mock_rag.return_value = {
            "answer": "The monthly rent is $2000.",
            "sources": ["sample chunk"],
            "chunk_count": 1,
            "reranked": False,
        }

        response = api_client.post(
            "/api/v1/query",
            json={"question": "What is the monthly rent amount?"},
        )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "chunk_count" in data
    assert "reranked" in data
    assert "latency_ms" in data
    assert "request_id" in data

    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0
    assert isinstance(data["sources"], list)
    assert data["latency_ms"] > 0


def test_ingest_path_returns_404_for_missing_file(api_client):
    """Non-existent file path must return 404, not 500."""
    response = api_client.post(
        "/api/v1/ingest/path",
        json={"pdf_path": "/does/not/exist/file.pdf"},
    )
    assert response.status_code == 404


def test_metrics_endpoint_returns_expected_keys(api_client):
    """
    GET /metrics must return latencies, counters, errors, and cost.
    This confirms the observability layer is wired into the app.
    """
    # Make a query first so metrics have data
    api_client.post("/api/v1/query", json={"question": "What is the rent amount?"})

    response = api_client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()

    assert "latencies"  in data
    assert "counters"   in data
    assert "errors"     in data
    assert "cost"       in data
    assert "today_usd"  in data["cost"]


def test_query_503_when_no_chunks_loaded(mock_pinecone, mock_openai, mock_cohere):
    """
    If no documents have been ingested, /query must return 503
    (service unavailable) not 500 (server error).
    
    This tests a real production scenario: someone deploys the API
    and queries before ingesting any documents.
    """
    from src.api.main import app
    from src.api import dependencies

    # Start with empty chunks
    dependencies._chunks = []
    dependencies._vectorstore = mock_pinecone

    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/query",
            json={"question": "What is the rent amount?"},
        )

    assert response.status_code == 503
    assert "No documents ingested" in response.json()["detail"]