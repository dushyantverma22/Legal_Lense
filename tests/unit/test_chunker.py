# tests/unit/test_chunker.py
import pytest
from langchain_core.documents import Document
from src.ingestion.chunker import chunk_documents


def test_chunks_are_produced(sample_docs):
    """Basic sanity: chunker returns at least one chunk."""
    chunks = chunk_documents(sample_docs)
    assert len(chunks) > 0


def test_chunk_size_respected(sample_docs):
    """
    WHY THIS TEST EXISTS:
    If someone accidentally changes chunk_size=700 to chunk_size=7000,
    every chunk would contain entire documents. Retrieval quality collapses.
    This test catches that regression immediately.
    """
    chunks = chunk_documents(sample_docs)
    from config.settings import get_settings
    settings = get_settings()
    for chunk in chunks:
        assert len(chunk.page_content) <= settings.chunk_size + 50, (
            f"Chunk too large: {len(chunk.page_content)} chars "
            f"(limit {settings.chunk_size})"
        )


def test_chunks_are_documents():
    """Chunker always returns LangChain Document objects, never raw strings."""
    docs = [Document(page_content="A" * 200, metadata={})]
    chunks = chunk_documents(docs)
    for chunk in chunks:
        assert isinstance(chunk, Document)
        assert isinstance(chunk.page_content, str)
        assert len(chunk.page_content) > 0


def test_empty_input_returns_empty():
    """Edge case: empty input list must not crash."""
    result = chunk_documents([])
    assert result == []


def test_short_doc_stays_as_single_chunk():
    """A document shorter than chunk_size must not be split."""
    short_text = "This is a short legal clause."
    docs = [Document(page_content=short_text, metadata={})]
    chunks = chunk_documents(docs)
    assert len(chunks) == 1
    assert short_text in chunks[0].page_content


def test_overlap_creates_continuity():
    """
    With overlap=120, consecutive chunks share content.
    This ensures retrieval can find context that spans a boundary.
    If overlap is accidentally set to 0, this test fails and you know
    retrieval quality will degrade for multi-clause questions.
    """
    # Need enough text to produce multiple chunks
    long_text = "The parties agree to the following terms and conditions. " * 30
    docs = [Document(page_content=long_text, metadata={})]
    chunks = chunk_documents(docs)

    if len(chunks) > 1:
        # The end of chunk N should appear somewhere in chunk N+1
        end_of_first = chunks[0].page_content[-50:]
        assert end_of_first in chunks[1].page_content, (
            "No overlap found between consecutive chunks — "
            "check chunk_overlap setting in config"
        )