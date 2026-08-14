from fastapi import APIRouter

from app.embeddings.embedder import embed_query
from app.schemas.search import SearchHit, SearchRequest, SearchResponse
from app.vector_db import store as vector_store

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def semantic_search(request: SearchRequest):
    """Find the chunks that mean the closest thing to the query.

    This is not keyword matching - the query is embedded with the same model
    the documents were, so "how do I renew my licence" can match a passage that
    never uses the word "renew".
    """
    vector = embed_query(request.query)
    hits = vector_store.search(
        vector=vector,
        limit=request.limit,
        document_id=request.document_id
    )

    return SearchResponse(
        query=request.query,
        count=len(hits),
        results=[SearchHit(**hit) for hit in hits]
    )


@router.get("/stats")
def search_stats():
    return {
        "indexed_chunks": vector_store.count()
    }
