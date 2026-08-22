import json

import pytest

from app.rag import bm25


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """A tiny corpus written to disk, since the index is built by reading it."""
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    (chunks / "doc1.json").write_text(
        json.dumps([
            {"document_id": "doc1", "original_filename": "a.pdf",
             "chunk_index": 0, "page": 1,
             "text": "The applicant must state their blood group and address."},
            {"document_id": "doc1", "original_filename": "a.pdf",
             "chunk_index": 1, "page": 2,
             "text": "Breadth first search explores a graph level by level."},
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(bm25, "CHUNKS_DIR", chunks)
    bm25.invalidate()
    yield
    bm25.invalidate()


def test_tokenize_drops_stopwords_and_single_characters():
    assert bm25.tokenize("The a of blood group") == ["blood", "group"]


def test_finds_the_passage_containing_the_literal_terms(corpus):
    hits = bm25.get_index().search("blood group", limit=5)
    assert hits, "expected a keyword match"
    assert "blood group" in hits[0]["text"].lower()


def test_ranks_by_relevance_not_by_order(corpus):
    hits = bm25.get_index().search("graph traversal level", limit=5)
    assert hits[0]["chunk_index"] == 1


def test_unmatched_query_returns_nothing(corpus):
    assert bm25.get_index().search("helicopter maintenance", limit=5) == []


def test_stopword_only_query_returns_nothing(corpus):
    assert bm25.get_index().search("the of and", limit=5) == []


def test_invalidate_forces_a_rebuild(corpus):
    first = bm25.get_index()
    bm25.invalidate()
    assert bm25.get_index() is not first
