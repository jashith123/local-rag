import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.documents import router as document_router
from app.api.search import router as search_router
from app.api.chat import router as chat_router
from app.api.suggestions import router as suggestions_router


def _warm_embedding_model() -> None:
    """Load the embedding model so the first real request doesn't have to.

    Cold-loading MiniLM takes ~30 seconds. Without this, the first /search after
    a restart blocks for that long and the frontend's proxy gives up on it.
    """
    try:
        from app.embeddings.embedder import get_model

        get_model()

        # The reranker is a second model with the same cold-start problem.
        from app.core.config import RERANK_ENABLED

        if RERANK_ENABLED:
            from app.rag.reranker import get_model as get_reranker

            get_reranker()
    except Exception:
        # Never stop the API from starting over this - the first search will
        # just pay the load cost itself.
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Daemon thread, so warming never delays startup or blocks shutdown.
    threading.Thread(target=_warm_embedding_model, daemon=True).start()
    yield


app = FastAPI(
    title="Enterprise AI Platform",
    version="0.0.1",
    lifespan=lifespan
)


@app.get("/")
def home():
    return {
        "status": "running",
        "project": "Enterprise AI Platform",
        "version": "0.0.1"
    }


app.include_router(health_router)
app.include_router(document_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(suggestions_router)
