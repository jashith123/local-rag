import threading

from app.core.config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL

# Loading the model takes a few seconds and ~100 MB of RAM, so we do it once,
# on first use, rather than at import time - otherwise the API would be slow to
# start and would download the model even for requests that never embed anything.
_model = None
_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _lock:
            # Checked twice on purpose: two requests can both pass the outer
            # check, and only one of them should pay for loading the model.
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Turn chunk texts into vectors. Batched - one call for the whole list."""
    if not texts:
        return []

    vectors = get_model().encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=False
    )
    return [vector.tolist() for vector in vectors]


def embed_query(text: str) -> list[float]:
    """Embed a search query.

    The query must go through the same model as the documents did - vectors
    from two different models are not comparable, however similar the text is.
    """
    return embed_texts([text])[0]


def dimensions() -> int:
    return EMBEDDING_DIMENSIONS
