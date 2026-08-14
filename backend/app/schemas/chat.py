from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.search import SearchHit


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=20, description="Passages to retrieve")
    document_id: Optional[str] = Field(
        None,
        description="Restrict the answer to a single document"
    )


class ChatUsage(BaseModel):
    input_tokens: int
    output_tokens: int


class ChatResponse(BaseModel):
    question: str
    answer: str
    # Returned in the same order they were numbered in the prompt, so [1] in
    # the answer text lines up with sources[0] in the UI.
    sources: list[SearchHit]
    provider: str
    model: str
    #: False for local models — the UI only shows a cost when it's real.
    billed: bool
    usage: Optional[ChatUsage] = None
