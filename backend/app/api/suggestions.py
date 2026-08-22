import json
import threading

from fastapi import APIRouter

from app.core.config import CHUNKS_DIR
from app.llm.base import LLMError
from app.llm.provider import get_provider
from app.services import document_store

router = APIRouter(prefix="/suggestions", tags=["suggestions"])

SYSTEM = (
    "You write a single short question that the given passage answers. "
    "Reply with the question only - no preamble, no quotes, no numbering. "
    "Keep it under 12 words and phrase it the way a person would type it "
    "into a search box."
)

# Generating a question per document costs a model call each, so the result is
# cached against the set of indexed documents and only rebuilt when that set
# changes.
_lock = threading.Lock()
_signature: tuple[str, ...] | None = None
_cached: list[str] = []


def _first_chunk(document_id: str) -> str | None:
    chunk_file = CHUNKS_DIR / f"{document_id}.json"
    if not chunk_file.exists():
        return None
    try:
        records = json.loads(chunk_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not records:
        return None
    # One chunk is plenty of signal, and keeps the prompt small enough to stay
    # fast on a local model.
    return records[0]["text"][:800]


def _fallback(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
    return f"What is {stem} about?"


def _clean(text: str, filename: str) -> str:
    question = text.strip().strip('"').strip()
    # Small models sometimes answer with a label or a numbered list despite
    # being told not to.
    for prefix in ("Question:", "Q:", "1.", "-"):
        if question.startswith(prefix):
            question = question[len(prefix):].strip()
    question = question.splitlines()[0].strip() if question else ""
    if not question or len(question) > 120:
        return _fallback(filename)
    return question


def _generate() -> list[str]:
    documents = [d for d in document_store.list_all() if d.status == "processed"]
    if not documents:
        return []

    # One question per document, and only for distinct files — the same PDF
    # uploaded twice shouldn't produce the same suggestion twice.
    seen_names: set[str] = set()
    questions: list[str] = []

    for document in documents:
        if document.original_filename in seen_names:
            continue
        seen_names.add(document.original_filename)

        passage = _first_chunk(document.document_id)
        if not passage:
            questions.append(_fallback(document.original_filename))
            continue

        try:
            answer, _ = get_provider().complete(
                SYSTEM,
                [{"role": "user", "content": "Passage:\n" + passage}],
            )
            questions.append(_clean(answer, document.original_filename))
        except (LLMError, Exception):
            # No model configured, or it failed - a filename-derived question
            # is still better than a hardcoded example about someone else's docs.
            questions.append(_fallback(document.original_filename))

    return questions


@router.get("")
def suggestions():
    """Example questions drawn from the documents that are actually indexed."""
    global _signature, _cached

    documents = [d for d in document_store.list_all() if d.status == "processed"]
    signature = tuple(sorted(d.document_id for d in documents))

    if signature == _signature:
        return {"suggestions": _cached, "generated": False}

    with _lock:
        # Another request may have rebuilt it while we waited for the lock.
        if signature == _signature:
            return {"suggestions": _cached, "generated": False}

        _cached = _generate()
        _signature = signature

    return {"suggestions": _cached, "generated": True}
