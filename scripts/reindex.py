"""Re-embed and re-index every document that already has chunks on disk.

Use this after changing the embedding model, after switching between embedded
Qdrant and a Qdrant server, or to index documents that were uploaded before the
vector stage existed.

    cd backend
    .venv/Scripts/python.exe ../scripts/reindex.py

The API server must be stopped first when running against embedded Qdrant -
it holds an exclusive lock on the storage folder.
"""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.config import CHUNKS_DIR  # noqa: E402
from app.embeddings.embedder import embed_texts  # noqa: E402
from app.services import document_store  # noqa: E402
from app.vector_db import store as vector_store  # noqa: E402


def main() -> int:
    documents = document_store.list_all()
    if not documents:
        print("No documents in the store - nothing to index.")
        return 0

    total = 0
    for document in documents:
        chunk_file = CHUNKS_DIR / f"{document.document_id}.json"
        if not chunk_file.exists():
            print(f"skip  {document.original_filename}: no chunk file")
            continue

        records = json.loads(chunk_file.read_text(encoding="utf-8"))
        chunks = [record["text"] for record in records]
        if not chunks:
            print(f"skip  {document.original_filename}: no chunks")
            continue

        vectors = embed_texts(chunks)
        indexed = vector_store.index_chunks(
            document_id=document.document_id,
            original_filename=document.original_filename,
            chunks=chunks,
            vectors=vectors
        )
        document_store.update(
            document.document_id,
            status="processed",
            vector_count=indexed,
            error=None
        )
        total += indexed
        print(f"ok    {document.original_filename}: {indexed} chunks indexed")

    print(f"\nDone. {total} chunks indexed. Collection now holds {vector_store.count()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
