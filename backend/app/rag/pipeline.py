import json
from pathlib import Path

from app.core.config import CHUNKS_DIR
from app.embeddings.embedder import embed_texts
from app.rag.chunking import chunk_text
from app.services import document_store
from app.services.pdf_service import extract_pages
from app.vector_db import store as vector_store


def _write_chunks(document_id: str, chunks: list[str]) -> Path:
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    chunk_file = CHUNKS_DIR / f"{document_id}.json"
    payload = [
        {"document_id": document_id, "chunk_index": index, "text": chunk}
        for index, chunk in enumerate(chunks)
    ]
    chunk_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return chunk_file


def process_document(document_id: str, file_path: Path) -> None:
    """Extract text from a stored PDF, chunk it, embed it, and index it.

    Runs in the background after the upload response has already been sent, so
    the user is not left staring at a spinner while a 300-page PDF is parsed and
    embedded. Every outcome is recorded on the document's status field - this
    function deliberately never raises, because nobody is left to catch it.
    """
    document_store.update(document_id, status="processing")

    try:
        pages = extract_pages(file_path)
        text = "\n\n".join(page for page in pages if page)
        chunks = chunk_text(text)
        _write_chunks(document_id, chunks)

        # Chunks on disk are the record; the vectors are the search index.
        document = document_store.get(document_id)
        original_filename = document.original_filename if document else "unknown"
        vectors = embed_texts(chunks)
        vector_count = vector_store.index_chunks(
            document_id=document_id,
            original_filename=original_filename,
            chunks=chunks,
            vectors=vectors
        )

        document_store.update(
            document_id,
            status="processed",
            page_count=len(pages),
            character_count=len(text),
            chunk_count=len(chunks),
            vector_count=vector_count,
            error=None
        )
    except Exception as exc:
        document_store.update(
            document_id,
            status="failed",
            error=str(exc)
        )
