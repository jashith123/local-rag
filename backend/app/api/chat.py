import json
from typing import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import RETRIEVAL_MODE
from app.llm.base import LLMError
from app.llm.provider import get_provider
from app.rag.prompt import SYSTEM_PROMPT, build_user_message
from app.rag.retrieval import retrieve as retrieve_passages
from app.schemas.chat import ChatRequest, ChatResponse, ChatUsage
from app.schemas.search import SearchHit

router = APIRouter(prefix="/chat", tags=["chat"])

# Returned without calling the model at all. Small models handed an empty
# context will still produce an answer, sometimes with invented citations —
# qwen2.5:3b answered "the documents don't say [1] [2]" with no passages in
# scope. Not asking is both cheaper and more truthful.
NO_CONTEXT_ANSWER = (
    "I couldn't find anything relevant to that in the indexed documents. "
    "Try rewording the question, or upload a document that covers it."
)


def retrieve(request: ChatRequest) -> list[dict]:
    """Fetch the passages worth showing the model.

    Hybrid by default, so a question phrased in the document's own words is
    caught by BM25 even when the embedding misses it.

    No score threshold is applied here any more: fused reciprocal-rank scores
    are on a different scale from cosine similarity (~0.03 vs ~0.5), so the old
    cutoff would have discarded everything. Relevance is instead controlled by
    how many passages we ask for.
    """
    return retrieve_passages(
        query=request.question,
        limit=request.top_k,
        document_id=request.document_id,
        mode=RETRIEVAL_MODE,
    )


@router.get("/config")
def chat_config():
    """What the UI needs to label answers and decide whether to show cost."""
    provider = get_provider()
    return {
        "provider": provider.name,
        "model": provider.model,
        "billed": provider.billed,
    }


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Answer a question from the indexed documents. Non-streaming."""
    provider = get_provider()
    hits = retrieve(request)

    if not hits:
        return ChatResponse(
            question=request.question,
            answer=NO_CONTEXT_ANSWER,
            sources=[],
            provider=provider.name,
            model=provider.model,
            billed=provider.billed,
        )

    try:
        answer, done = provider.complete(
            SYSTEM_PROMPT, build_user_message(request.question, hits)
        )
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return ChatResponse(
        question=request.question,
        answer=answer,
        sources=[SearchHit(**hit) for hit in hits],
        provider=provider.name,
        model=done["model"],
        billed=provider.billed,
        usage=ChatUsage(**done["usage"]),
    )


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@router.post("/stream")
def chat_stream(request: ChatRequest):
    """Same answer, streamed token by token over Server-Sent Events.

    Sources go first so the UI can render citations before any text arrives,
    then deltas, then a final usage event.
    """

    def generate() -> Iterator[str]:
        try:
            provider = get_provider()
            hits = retrieve(request)
        except LLMError as exc:
            yield _sse("error", {"message": str(exc)})
            return
        except Exception as exc:
            yield _sse("error", {"message": f"Retrieval failed: {exc}"})
            return

        yield _sse("sources", {"sources": hits})

        if not hits:
            yield _sse("delta", {"text": NO_CONTEXT_ANSWER})
            yield _sse(
                "done",
                {
                    "provider": provider.name,
                    "model": provider.model,
                    "billed": provider.billed,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            )
            return

        user_message = build_user_message(request.question, hits)

        try:
            for event, payload in provider.stream(SYSTEM_PROMPT, user_message):
                if event == "done":
                    payload = {
                        **payload,
                        "provider": provider.name,
                        "billed": provider.billed,
                    }
                yield _sse(event, payload)
        except LLMError as exc:
            # The response has already started, so the status code is fixed at
            # 200 — the only way left to report a failure is in the stream.
            yield _sse("error", {"message": str(exc)})
        except Exception as exc:
            yield _sse("error", {"message": f"Answer generation failed: {exc}"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Tell any reverse proxy in front of us not to buffer, which would
            # defeat the point by delivering the whole answer at once.
            "X-Accel-Buffering": "no",
        },
    )
