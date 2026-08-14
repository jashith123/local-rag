import hashlib
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    UploadFile,
    status
)

from app.core.config import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    CHUNKS_DIR,
    MAX_UPLOAD_SIZE,
    UPLOAD_DIRECTORY
)
from app.rag import bm25
from app.rag.pipeline import process_document
from app.vector_db import store as vector_store
from app.schemas.document import (
    DocumentListResponse,
    DocumentMetadata,
    UploadResponse
)
from app.services import document_store

router = APIRouter(prefix="/documents", tags=["documents"])

# Read the upload a megabyte at a time instead of all at once, so a 2 GB file
# costs us 1 MB of memory rather than 2 GB.
READ_CHUNK_SIZE = 1024 * 1024

# Every real PDF starts with these bytes.
PDF_MAGIC = b"%PDF-"


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    original_filename = Path(file.filename or "untitled").name
    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PDF files are allowed, got '{extension or 'no extension'}'"
        )

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected content type application/pdf, got '{file.content_type}'"
        )

    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # The stored name is a UUID, so two people uploading "resume.pdf" cannot
    # overwrite each other. It also means nothing the client typed ever reaches
    # the filesystem, which rules out "../../main.py" style filenames.
    document_id = str(uuid.uuid4())
    stored_filename = f"{document_id}{extension}"
    destination = UPLOAD_DIRECTORY / stored_filename

    size = 0
    digest = hashlib.sha256()
    try:
        with destination.open("wb") as buffer:
            while chunk := await file.read(READ_CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit"
                    )
                # Hashed as it streams past, so deduplication costs no extra
                # pass over the file.
                digest.update(chunk)
                buffer.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty"
            )

        # The extension and the content type both come from the client, so both
        # can lie. The file's own first bytes cannot - this is what actually
        # catches virus.exe renamed to virus.pdf.
        with destination.open("rb") as saved:
            if saved.read(len(PDF_MAGIC)) != PDF_MAGIC:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File is not a valid PDF (missing %PDF- header)"
                )
        # Same bytes as something already indexed? Indexing it twice doubles
        # every future search result for no benefit, so point the caller at
        # what they already have instead.
        content_hash = digest.hexdigest()
        existing = document_store.find_by_hash(content_hash)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"This file is already indexed as "
                    f"'{existing.original_filename}' "
                    f"({existing.document_id[:8]}). Delete that first to re-upload."
                )
            )
    except Exception:
        # Never leave a rejected or half-written upload sitting on disk.
        destination.unlink(missing_ok=True)
        raise

    document = DocumentMetadata(
        document_id=document_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        content_type=file.content_type,
        size=size,
        content_hash=content_hash,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        status="uploaded"
    )
    document_store.save(document)

    # Hand the slow work off and respond immediately. The client polls
    # GET /documents/{id} to watch status go processing -> processed.
    background_tasks.add_task(process_document, document_id, destination)

    return UploadResponse(
        message="File uploaded successfully",
        document=document
    )


@router.get("", response_model=DocumentListResponse)
def list_documents():
    documents = document_store.list_all()
    return DocumentListResponse(count=len(documents), documents=documents)


@router.get("/{document_id}", response_model=DocumentMetadata)
def get_document(document_id: str):
    document = document_store.get(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No document with id {document_id}"
        )
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str):
    """Remove a document and everything derived from it.

    Four places hold state for one document — the PDF, its chunk file, its
    vectors, and its metadata row. Deleting only some of them is how you end up
    with search results pointing at documents that no longer exist, so this
    removes all four.
    """
    document = document_store.get(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No document with id {document_id}"
        )

    (UPLOAD_DIRECTORY / document.stored_filename).unlink(missing_ok=True)
    (CHUNKS_DIR / f"{document_id}.json").unlink(missing_ok=True)

    # Best-effort on the vector store: if it fails, the metadata row should
    # still go, otherwise the UI shows a document the user cannot get rid of.
    try:
        vector_store.delete_document(document_id)
    except Exception:
        pass

    document_store.delete(document_id)
    bm25.invalidate()
    return None
