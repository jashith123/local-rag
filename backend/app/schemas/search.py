from typing import Literal, Optional

from pydantic import BaseModel, Field

RetrievalMode = Literal["hybrid", "vector", "keyword"]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language question")
    limit: int = Field(5, ge=1, le=50, description="How many chunks to return")
    document_id: Optional[str] = Field(
        None,
        description="Restrict the search to a single document"
    )
    mode: Optional[RetrievalMode] = Field(
        None,
        description="Override the configured retrieval mode (hybrid by default)"
    )


class SearchHit(BaseModel):
    # In hybrid mode this is the fused reciprocal-rank score, which is small
    # (~0.03) and only meaningful as an ordering. The per-retriever scores
    # below are the interpretable ones.
    score: float
    document_id: str
    original_filename: str
    chunk_index: int
    page: Optional[int] = None
    text: str

    #: Which retrievers found this passage — ["vector"], ["keyword"] or both.
    matched_by: list[str] = Field(default_factory=list)
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None
    #: Cross-encoder relevance, present only when reranking ran. Unbounded
    #: logit: positive is relevant, negative is not.
    rerank_score: Optional[float] = None


class SearchResponse(BaseModel):
    query: str
    mode: RetrievalMode
    reranked: bool
    count: int
    results: list[SearchHit]
