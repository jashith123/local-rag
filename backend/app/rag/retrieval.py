from typing import Literal, Optional

from app.core.config import RRF_K
from app.embeddings.embedder import embed_query
from app.rag import bm25
from app.vector_db import store as vector_store

Mode = Literal["hybrid", "vector", "keyword"]


def _key(hit: dict) -> tuple:
    return (hit["document_id"], hit["chunk_index"])


def _fuse(
    vector_hits: list[dict],
    keyword_hits: list[dict],
    limit: int,
) -> list[dict]:
    """Reciprocal rank fusion.

    The two retrievers produce scores on incompatible scales - cosine
    similarity sits around 0-1, BM25 is unbounded - so the scores cannot be
    added or averaged meaningfully. RRF throws the magnitudes away and uses
    only the *rank* each retriever assigned, which is the standard fix:

        score(d) = sum over retrievers of 1 / (k + rank(d))

    A passage both retrievers like outranks one that only a single retriever
    loved. k (60 by convention) damps the top ranks so that first place is not
    overwhelmingly decisive.
    """
    fused: dict[tuple, dict] = {}

    for source, hits in (("vector", vector_hits), ("keyword", keyword_hits)):
        for rank, hit in enumerate(hits, start=1):
            key = _key(hit)
            entry = fused.get(key)
            if entry is None:
                entry = {
                    **hit,
                    "rrf_score": 0.0,
                    "vector_score": None,
                    "keyword_score": None,
                    "matched_by": [],
                }
                fused[key] = entry

            entry["rrf_score"] += 1.0 / (RRF_K + rank)
            entry[f"{source}_score"] = hit["score"]
            entry["matched_by"].append(source)

    ranked = sorted(fused.values(), key=lambda h: h["rrf_score"], reverse=True)

    results = []
    for hit in ranked[:limit]:
        results.append(
            {
                "document_id": hit["document_id"],
                "original_filename": hit["original_filename"],
                "chunk_index": hit["chunk_index"],
                "page": hit.get("page"),
                "text": hit["text"],
                # `score` stays the primary sort value so every caller keeps
                # working; the per-retriever scores are exposed alongside it so
                # the UI can show *why* something matched.
                "score": hit["rrf_score"],
                "vector_score": hit["vector_score"],
                "keyword_score": hit["keyword_score"],
                "matched_by": hit["matched_by"],
            }
        )
    return results


def _keyword_search(
    query: str, limit: int, document_id: Optional[str]
) -> list[dict]:
    hits = bm25.get_index().search(query, limit=limit * 3 if document_id else limit)
    if document_id:
        hits = [h for h in hits if h["document_id"] == document_id][:limit]
    return hits


def retrieve(
    query: str,
    limit: int = 5,
    document_id: Optional[str] = None,
    mode: Mode = "hybrid",
) -> list[dict]:
    """Retrieve passages for a query.

    Each retriever is asked for more than `limit` before fusion, because a
    passage ranked 8th by one and 2nd by the other should still be able to win
    - and it can only do that if both lists are deep enough to contain it.
    """
    depth = max(limit * 4, 20)

    if mode == "vector":
        hits = vector_store.search(
            vector=embed_query(query), limit=limit, document_id=document_id
        )
        return [{**h, "matched_by": ["vector"], "vector_score": h["score"],
                 "keyword_score": None} for h in hits]

    if mode == "keyword":
        hits = _keyword_search(query, limit, document_id)
        return [{**h, "matched_by": ["keyword"], "keyword_score": h["score"],
                 "vector_score": None} for h in hits]

    vector_hits = vector_store.search(
        vector=embed_query(query), limit=depth, document_id=document_id
    )
    keyword_hits = _keyword_search(query, depth, document_id)
    return _fuse(vector_hits, keyword_hits, limit)
