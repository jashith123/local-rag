import re

from app.core.config import CHUNK_OVERLAP, CHUNK_SIZE

_WHITESPACE = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalize(text: str) -> str:
    text = _WHITESPACE.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Split text into overlapping chunks, preferring to break on whitespace.

    An embedding model has a fixed input limit, so a 40-page PDF cannot become
    one vector. It also should not become one vector per page: retrieval works
    best when each chunk covers roughly one idea.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = normalize(text)
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)

        # Don't slice a word in half. Back up to the last space in this window,
        # unless that would make the chunk absurdly short.
        if end < length:
            boundary = text.rfind(" ", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= length:
            break

        # max(..., start + 1) guarantees forward progress. Without it, a chunk
        # shorter than the overlap would make start move backwards forever.
        start = max(end - overlap, start + 1)

    return chunks
