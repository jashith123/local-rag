import json
from typing import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import CHAT_MIN_RERANK_SCORE, RETRIEVAL_MODE
from app.llm.base import LLMError, Message
from app.llm.provider import get_provider
from app.rag.prompt import SYSTEM_PROMPT, build_user_message
from app.rag.query_rewrite import rewrite
from app.rag.retrieval import retrieve as retrieve_passages
from app.schemas.chat import ChatRequest, ChatResponse, ChatUsage
from app.schemas.search import SearchHit

router = APIRouter(prefix="/chat", tags=["chat"])

# Returned without calling the model at all. Small models handed an empty or
# irrelevant context still produce an answer, often with invented citations -
# qwen3:4b-instruct answered "the documents do not provide information..."
# followed by [1][2][3][4][5]. Not asking is cheaper and more truthful.
NO_CONTEXT_ANSWER = (
    "I couldn't find anything relevant to that in the indexed documents. "
    "Try rewording the question, or upload a document that covers it."
)


def _history(request: ChatRequest) -> list[Message]:
    return [{"role": t.role, "content": t.content} for t in request.history]


def retrieve(request: ChatRequest) -> tuple[list[dict], str]:
    """Fetch the passages worth showing the model.

    Returns (passages, query_actually_searched). A follow-up is rewritten into
    a standalone question first: the generator can resolve "it" from the
    conversation, but the retriever only ever sees a string.

    Passages the reranker scores below the relevance gate are dropped. The
    model is told to ignore irrelevant passages, but the reliable way to stop
    it citing noise is to not send any.
    """
    query, _ = rewrite(request.question, _history(request))

    hits = retrieve_passages(
        query=query,
        limit=request.top_k,
        document_id=request.document_id,
        mode=RETRIEVAL_MODE,
    )

    relevant = [
        hit
        for hit in hits
        if hit.get("rerank_score") is None
        or hit["rerank_score"] >= CHAT_MIN_RERANK_SCORE
    ]
    return relevant, query


def _messages(request: ChatRequest, hits: list[dict]) -> list[Message]:
    """Conversation so far, then this question with its retrieved passages.

    Only the current turn carries passages. Re-sending the context of every
    previous turn would bury the question and blow past the context window.
    """
    return [
        *_history(request),
        {"role": "user", "content": build_user_message(request.question, hits)},
    ]


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
    hits, query = retrieve(request)

    if not hits:
        return ChatResponse(
            question=request.question,
            answer=NO_CONTEXT_ANSWER,
            sources=[],
            provider=provider.name,
            model=provider.model,
            search_query=query,
            billed=provider.billed,
        )

    try:
        answer, done = provider.complete(SYSTEM_PROMPT, _messages(request, hits))
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
        search_query=query,
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
            hits, query = retrieve(request)
        except LLMError as exc:
            yield _sse("error", {"message": str(exc)})
            return
        except Exception as exc:
            yield _sse("error", {"message": f"Retrieval failed: {exc}"})
            return

        yield _sse("sources", {"sources": hits, "search_query": query})

        if not hits:
            yield _sse("delta", {"text": NO_CONTEXT_ANSWER})
            yield _sse(
                "done",
                {
                    "provider": provider.name,
                    "model": provider.model,
                    "billed": provider.billed,
                    "search_query": query,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            )
            return

        try:
            for event, payload in provider.stream(
                SYSTEM_PROMPT, _messages(request, hits)
            ):
                if event == "done":
                    payload = {
                        **payload,
                        "provider": provider.name,
                        "billed": provider.billed,
                        "search_query": query,
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
