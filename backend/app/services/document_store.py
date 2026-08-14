import json
import threading
from typing import Optional

from app.core.config import DOCUMENT_DB_FILE, STORAGE_DIR
from app.schemas.document import DocumentMetadata

# A JSON file standing in for PostgreSQL until Phase 4. Every function here is
# the shape a real repository would have, so swapping the storage underneath
# should not change any caller.

# Background tasks run in a worker thread, so two of them can finish at the
# same moment. Without this lock the second write would clobber the first.
_lock = threading.Lock()


def _read_all() -> dict[str, dict]:
    if not DOCUMENT_DB_FILE.exists():
        return {}
    try:
        return json.loads(DOCUMENT_DB_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt index should not take the whole API down.
        return {}


def _write_all(records: dict[str, dict]) -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    # Write to a temp file and rename, so a crash mid-write cannot leave a
    # half-written index behind.
    temp_file = DOCUMENT_DB_FILE.with_name(DOCUMENT_DB_FILE.name + ".tmp")
    temp_file.write_text(json.dumps(records, indent=2), encoding="utf-8")
    temp_file.replace(DOCUMENT_DB_FILE)


def save(document: DocumentMetadata) -> DocumentMetadata:
    with _lock:
        records = _read_all()
        records[document.document_id] = document.model_dump()
        _write_all(records)
    return document


def update(document_id: str, **fields) -> Optional[DocumentMetadata]:
    with _lock:
        records = _read_all()
        if document_id not in records:
            return None
        records[document_id].update(fields)
        _write_all(records)
        return DocumentMetadata(**records[document_id])


def get(document_id: str) -> Optional[DocumentMetadata]:
    records = _read_all()
    record = records.get(document_id)
    return DocumentMetadata(**record) if record else None


def find_by_hash(content_hash: str) -> Optional[DocumentMetadata]:
    """Find an already-indexed document with identical bytes, if any."""
    for record in _read_all().values():
        if record.get("content_hash") == content_hash:
            return DocumentMetadata(**record)
    return None


def delete(document_id: str) -> bool:
    with _lock:
        records = _read_all()
        if document_id not in records:
            return False
        del records[document_id]
        _write_all(records)
        return True


def list_all() -> list[DocumentMetadata]:
    records = _read_all()
    documents = [DocumentMetadata(**record) for record in records.values()]
    return sorted(documents, key=lambda doc: doc.uploaded_at, reverse=True)
