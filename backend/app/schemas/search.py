from typing import Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language question")
    limit: int = Field(5, ge=1, le=50, description="How many chunks to return")
    document_id: Optional[str] = Field(
        None,
        description="Restrict the search to a single document"
    )


class SearchHit(BaseModel):
    # 1.0 is an exact match. With cosine distance on normalized vectors,
    # anything above ~0.5 is usually genuinely related.
    score: float
    document_id: str
    original_filename: str
    chunk_index: int
    text: str


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[SearchHit]
