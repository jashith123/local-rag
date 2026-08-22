from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.search import SearchHit


class ChatTurn(BaseModel):
    #: "user" or "assistant"
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    #: Prior turns, oldest first. Without these a follow-up like "how fast is
    #: it" has no referent and retrieval goes looking for the wrong thing.
    history: list[ChatTurn] = Field(default_factory=list)
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
    #: The standalone question actually used for retrieval. Differs from
    #: `question` when a follow-up had to be resolved against the history.
    search_query: Optional[str] = None
    #: False for local models — the UI only shows a cost when it's real.
    billed: bool
    usage: Optional[ChatUsage] = None
