# tests/integration/test_pipeline.py
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from src.ingestion.chunker import chunk_documents
from src.ingestion.embedder import _make_vector_id


def test_chunker_output_feeds_into_embedder(sample_docs):
    """
    INTEGRATION: chunker output is valid input for the embedder.
    
    WHY: If chunker changes its output format (e.g. returns None
    page_content on empty pages), the embedder will crash with a
    cryptic error. This test catches the interface mismatch directly.
    """
    chunks = chunk_documents(sample_docs)
    assert len(chunks) > 0

    # Every chunk must be embeddable: non-empty string content
    for i, chunk in enumerate(chunks):
        assert chunk.page_content, f"Chunk {i} has empty page_content"
        assert isinstance(chunk.page_content, str)

        # Must be able to generate a stable vector ID
        vector_id = _make_vector_id("test.pdf", i, chunk.page_content)
        assert len(vector_id) == 32


def test_hybrid_retrieve_returns_documents(sample_chunks, mock_pinecone):
    """
    INTEGRATION: hybrid_retrieve() returns Document objects.
    Pinecone is mocked — tests the merging/ranking logic, not the API.
    """
    from src.retrieval.hybrid import hybrid_retrieve

    # BM25 needs real chunks; Pinecone is mocked
    results = hybrid_retrieve(
        query="What is the rent amount?",
        chunks=sample_chunks,
        vectorstore=mock_pinecone,
        top_k=3,
    )

    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(doc, Document) for doc in results)


def test_rerank_falls_back_gracefully_when_cohere_fails(sample_chunks):
    """
    INTEGRATION: if Cohere raises an exception, rerank_documents()
    must return hybrid results rather than propagating the error.
    
    This is the graceful degradation test — confirms the circuit
    breaker fallback actually works end-to-end.
    """
    from src.retrieval.hybrid import rerank_documents

    with patch("cohere.Client") as mock_cohere_class:
        mock_client = MagicMock()
        mock_client.rerank.side_effect = Exception("Cohere service unavailable")
        mock_cohere_class.return_value = mock_client

        # Must not raise — must return a list
        result = rerank_documents(
            query="rent amount",
            docs=sample_chunks[:5],
            top_n=3,
        )

    assert isinstance(result, list)
    assert len(result) <= 5    # got some results, not an error


def test_full_query_pipeline_returns_answer(sample_chunks, mock_pinecone, mock_cohere):
    """
    INTEGRATION: the full run_rag_query() pipeline returns a proper dict.
    OpenAI LLM is mocked to return a predictable answer.
    """
    from src.generation.chain import run_rag_query

    fake_llm_response = MagicMock()
    fake_llm_response.content = "The rent is Rs. 17,600/- per month."

    with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = fake_llm_response
        mock_llm_class.return_value = mock_llm

        result = run_rag_query(
            query="What is the monthly rent?",
            chunks=sample_chunks,
            vectorstore=mock_pinecone,
        )

    assert isinstance(result, dict)
    assert "answer" in result
    assert "sources" in result
    assert "chunk_count" in result
    assert "reranked" in result
    assert len(result["answer"]) > 0
    assert isinstance(result["sources"], list)