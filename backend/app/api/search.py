from fastapi import APIRouter

from app.core.config import RETRIEVAL_MODE
from app.rag.retrieval import retrieve
from app.schemas.search import SearchHit, SearchRequest, SearchResponse
from app.vector_db import store as vector_store

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def semantic_search(request: SearchRequest):
    """Find the passages that best answer the query.

    Hybrid by default: embeddings catch paraphrases the words don't share,
    BM25 catches the literal terms embeddings gloss over, and reciprocal rank
    fusion merges the two orderings.
    """
    mode = request.mode or RETRIEVAL_MODE
    hits = retrieve(
        query=request.query,
        limit=request.limit,
        document_id=request.document_id,
        mode=mode,
    )

    return SearchResponse(
        query=request.query,
        mode=mode,
        count=len(hits),
        results=[SearchHit(**hit) for hit in hits],
    )


@router.get("/stats")
def search_stats():
    from app.rag import bm25

    return {
        "indexed_chunks": vector_store.count(),
        "keyword_index_size": len(bm25.get_index().documents),
        "mode": RETRIEVAL_MODE,
    }
