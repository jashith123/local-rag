import threading

from app.core.config import RERANK_MODEL

# A cross-encoder reads the query and the passage *together* and scores the
# pair, instead of comparing two independently-computed vectors. That is much
# more accurate and much slower - which is exactly why it runs second, over the
# ~20 candidates retrieval already narrowed to, rather than over the corpus.
_model = None
_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import CrossEncoder

                _model = CrossEncoder(RERANK_MODEL)
    return _model


def rerank(query: str, hits: list[dict], limit: int) -> list[dict]:
    """Re-order candidates by cross-encoder relevance and keep the best.

    Returns the hits unchanged if the model can't be loaded: a reranker is an
    improvement on retrieval, not a dependency of it, and search going down
    because an optional model failed to download would be the wrong trade.
    """
    if not hits:
        return []
    if len(hits) == 1:
        return hits[:limit]

    try:
        model = get_model()
        scores = model.predict(
            [(query, hit["text"]) for hit in hits],
            show_progress_bar=False,
        )
    except Exception:
        return hits[:limit]

    scored = [
        {**hit, "rerank_score": float(score)} for hit, score in zip(hits, scores)
    ]
    scored.sort(key=lambda hit: hit["rerank_score"], reverse=True)
    return scored[:limit]
