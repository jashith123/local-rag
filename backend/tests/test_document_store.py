import pytest

from app.schemas.document import DocumentMetadata
from app.services import document_store


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(document_store, "DOCUMENT_DB_FILE", tmp_path / "documents.json")
    monkeypatch.setattr(document_store, "STORAGE_DIR", tmp_path)
    yield


def make(document_id="d1", name="a.pdf", content_hash="abc123"):
    return DocumentMetadata(
        document_id=document_id,
        original_filename=name,
        stored_filename=f"{document_id}.pdf",
        content_type="application/pdf",
        size=100,
        content_hash=content_hash,
        uploaded_at="2026-01-01T00:00:00+00:00",
        status="uploaded",
    )


def test_save_then_get_round_trips(store):
    document_store.save(make())
    assert document_store.get("d1").original_filename == "a.pdf"


def test_get_unknown_id_returns_none(store):
    assert document_store.get("missing") is None


def test_update_changes_only_the_named_fields(store):
    document_store.save(make())
    document_store.update("d1", status="processed", chunk_count=7)
    doc = document_store.get("d1")
    assert doc.status == "processed"
    assert doc.chunk_count == 7
    assert doc.original_filename == "a.pdf"


def test_update_unknown_id_returns_none(store):
    assert document_store.update("missing", status="processed") is None


def test_find_by_hash_matches_identical_bytes(store):
    document_store.save(make())
    found = document_store.find_by_hash("abc123")
    assert found is not None and found.document_id == "d1"


def test_find_by_hash_ignores_a_different_file(store):
    document_store.save(make())
    assert document_store.find_by_hash("different") is None


def test_documents_without_a_hash_do_not_match(store):
    """Documents indexed before hashing existed must not collide on None."""
    document_store.save(make(content_hash=None))
    assert document_store.find_by_hash(None) is None


def test_delete_removes_the_record(store):
    document_store.save(make())
    assert document_store.delete("d1") is True
    assert document_store.get("d1") is None


def test_delete_unknown_id_is_false(store):
    assert document_store.delete("missing") is False


def test_a_corrupt_store_does_not_raise(store, tmp_path):
    (tmp_path / "documents.json").write_text("{not json", encoding="utf-8")
    assert document_store.list_all() == []
