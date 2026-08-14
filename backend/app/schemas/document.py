from typing import Literal, Optional

from pydantic import BaseModel

# Where a document is in the ingestion pipeline.
#   uploaded  -> file is on disk, nothing read yet
#   processing-> background task is extracting, chunking and embedding
#   processed -> chunks embedded and stored in Qdrant, searchable
#   failed    -> something in the pipeline blew up, see `error`
DocumentStatus = Literal["uploaded", "processing", "processed", "failed"]


class DocumentMetadata(BaseModel):
    document_id: str
    original_filename: str
    stored_filename: str
    content_type: str
    size: int
    uploaded_at: str
    status: DocumentStatus = "uploaded"
    page_count: Optional[int] = None
    character_count: Optional[int] = None
    chunk_count: Optional[int] = None
    vector_count: Optional[int] = None
    error: Optional[str] = None


class UploadResponse(BaseModel):
    message: str
    document: DocumentMetadata


class DocumentListResponse(BaseModel):
    count: int
    documents: list[DocumentMetadata]
