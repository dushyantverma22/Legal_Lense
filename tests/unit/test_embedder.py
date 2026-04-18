# tests/unit/test_embedder.py
import pytest
from src.ingestion.embedder import _make_vector_id


def test_same_inputs_produce_same_id():
    """
    IDEMPOTENCY TEST — the most critical unit test in the project.
    
    WHY: If _make_vector_id returns a different ID each time for the
    same chunk, Pinecone upserts will CREATE new vectors instead of
    overwriting, silently duplicating your entire index on every re-run.
    
    This was the bug in the original notebook. This test ensures it
    can never come back.
    """
    id1 = _make_vector_id("data/raw/rent.pdf", 0, "The lessee shall pay rent")
    id2 = _make_vector_id("data/raw/rent.pdf", 0, "The lessee shall pay rent")
    assert id1 == id2, "Same input must always produce same vector ID"


def test_different_pdfs_produce_different_ids():
    """Two different PDFs must never share a vector ID."""
    id1 = _make_vector_id("data/raw/rent.pdf",    0, "The lessee shall pay rent")
    id2 = _make_vector_id("data/raw/another.pdf", 0, "The lessee shall pay rent")
    assert id1 != id2


def test_different_chunk_indexes_produce_different_ids():
    """
    Chunk 0 and chunk 1 from the same PDF must have different IDs,
    even if their text is identical (repeated clauses in legal docs).
    """
    id1 = _make_vector_id("data/raw/rent.pdf", 0, "Standard clause text.")
    id2 = _make_vector_id("data/raw/rent.pdf", 1, "Standard clause text.")
    assert id1 != id2


def test_id_is_string_of_expected_length():
    """MD5 hex digest is always 32 characters."""
    vector_id = _make_vector_id("test.pdf", 0, "some content")
    assert isinstance(vector_id, str)
    assert len(vector_id) == 32


def test_id_contains_only_hex_chars():
    """Pinecone IDs must be alphanumeric — no special characters."""
    import re
    vector_id = _make_vector_id("test.pdf", 0, "some content")
    assert re.match(r'^[0-9a-f]+$', vector_id), (
        f"Vector ID '{vector_id}' contains non-hex characters"
    )