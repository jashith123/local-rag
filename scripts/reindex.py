"""Re-embed and re-index every document that already has chunks on disk.

Use this after changing the embedding model, after switching between embedded
Qdrant and a Qdrant server, or to index documents that were uploaded before the
vector stage existed.

    cd backend
    .venv/Scripts/python.exe ../scripts/reindex.py

The API server must be stopped first when running against embedded Qdrant -
it holds an exclusive lock on the storage folder.
"""
import hashlib
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.config import UPLOAD_DIRECTORY  # noqa: E402
from app.embeddings.embedder import embed_texts  # noqa: E402
from app.rag import bm25  # noqa: E402
from app.rag.chunking import chunk_pages  # noqa: E402
from app.rag.pipeline import _write_chunks  # noqa: E402
from app.services import document_store  # noqa: E402
from app.services.pdf_service import extract_pages  # noqa: E402
from app.vector_db import store as vector_store  # noqa: E402


def main() -> int:
    documents = document_store.list_all()
    if not documents:
        print("No documents in the store - nothing to index.")
        return 0

    total = 0
    for document in documents:
        # Re-extract from the PDF rather than reusing the chunk file, so a
        # change to the chunker (page tracking, sizes) actually takes effect.
        pdf = UPLOAD_DIRECTORY / document.stored_filename
        if not pdf.exists():
            print(f"skip  {document.original_filename}: source PDF missing")
            continue

        try:
            records = chunk_pages(extract_pages(pdf))
        except Exception as exc:
            print(f"fail  {document.original_filename}: {exc}")
            continue

        if not records:
            print(f"skip  {document.original_filename}: no text extracted")
            continue

        _write_chunks(document.document_id, document.original_filename, records)

        # Backfill the content hash for documents indexed before deduplication
        # existed — without it, re-uploading them is not caught.
        if not document.content_hash:
            digest = hashlib.sha256()
            with pdf.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            document_store.update(
                document.document_id, content_hash=digest.hexdigest()
            )
        chunks = [record["text"] for record in records]

        vectors = embed_texts(chunks)
        indexed = vector_store.index_chunks(
            document_id=document.document_id,
            original_filename=document.original_filename,
            records=records,
            vectors=vectors
        )
        document_store.update(
            document.document_id,
            status="processed",
            page_count=len(records) and max(r["page"] for r in records),
            character_count=sum(len(c) for c in chunks),
            chunk_count=len(records),
            vector_count=indexed,
            error=None
        )
        total += indexed
        pages = max(r["page"] for r in records)
        print(
            f"ok    {document.original_filename}: {indexed} chunks "
            f"across {pages} page(s)"
        )

    bm25.invalidate()
    print(f"\nDone. {total} chunks indexed. Collection now holds {vector_store.count()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
