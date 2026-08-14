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


def chunk_pages(
    pages: list[str],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> list[dict]:
    """Chunk a document while keeping track of which page each chunk came from.

    Chunking the whole document as one string loses the page boundaries, and a
    citation that says "page 4" is far more checkable than one that says
    "chunk 7". Each page is chunked on its own, so a chunk never straddles two
    pages and its page number is always exact.

    The tradeoff is that a passage spanning a page break gets split, which the
    overlap can't repair across pages. That is worth it: page-accurate
    citations are the thing a reader can actually verify.
    """
    records: list[dict] = []

    for page_number, page_text in enumerate(pages, start=1):
        for chunk in chunk_text(page_text, chunk_size, overlap):
            records.append({"text": chunk, "page": page_number})

    return records
