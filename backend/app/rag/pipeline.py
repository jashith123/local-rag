import json
from pathlib import Path

from app.core.config import CHUNKS_DIR
from app.embeddings.embedder import embed_texts
from app.rag import bm25
from app.rag.chunking import chunk_pages
from app.services import document_store
from app.services.pdf_service import extract_pages
from app.vector_db import store as vector_store


def _write_chunks(
    document_id: str, original_filename: str, records: list[dict]
) -> Path:
    """Write the chunk file.

    The filename is denormalised in here on purpose: the BM25 index is built by
    reading these files, and a search result has to be able to say which
    document it came from without a second lookup.
    """
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    chunk_file = CHUNKS_DIR / f"{document_id}.json"
    payload = [
        {
            "document_id": document_id,
            "original_filename": original_filename,
            "chunk_index": index,
            "page": record["page"],
            "text": record["text"],
        }
        for index, record in enumerate(records)
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
        # Chunk page by page so every chunk knows the page it came from, which
        # is what makes a citation checkable.
        records = chunk_pages(pages)

        document = document_store.get(document_id)
        original_filename = document.original_filename if document else "unknown"
        _write_chunks(document_id, original_filename, records)

        texts = [record["text"] for record in records]
        vectors = embed_texts(texts)
        vector_count = vector_store.index_chunks(
            document_id=document_id,
            original_filename=original_filename,
            records=records,
            vectors=vectors,
        )

        # The keyword index reads the chunk files, so it must be rebuilt now
        # that there are new ones - otherwise search silently misses this
        # document until the process restarts.
        bm25.invalidate()

        document_store.update(
            document_id,
            status="processed",
            page_count=len(pages),
            character_count=sum(len(text) for text in texts),
            chunk_count=len(records),
            vector_count=vector_count,
            error=None,
        )
    except Exception as exc:
        document_store.update(document_id, status="failed", error=str(exc))
