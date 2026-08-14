import json
import math
import re
import threading
from collections import Counter

from app.core.config import CHUNKS_DIR

# Standard BM25 constants. k1 controls how quickly repeated terms stop adding
# score; b controls how strongly long passages are penalised.
K1 = 1.5
B = 0.75

_TOKEN = re.compile(r"[a-z0-9]+")

# Words so common they match everything and rank nothing. Kept deliberately
# short - an aggressive list would drop terms that matter in a form ("no",
# "name") more often than it would help.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "been", "it", "its", "this", "that", "these", "those",
    "as", "at", "by", "with", "from", "what", "which", "who", "how", "why",
    "do", "does", "did", "i", "you", "we", "they",
}


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN.findall(text.lower())
        if token not in _STOPWORDS and len(token) > 1
    ]


class BM25Index:
    """An in-memory BM25 index over the chunk files on disk.

    Why this exists: embeddings are weak on form-like and tabular text. A query
    for "blood group" failed to retrieve the chunk that literally contains the
    words "Blood Group", because that passage is a bag of field labels with
    little semantic shape. Keyword scoring catches exactly that case.

    Why it's in-process rather than in Qdrant: the corpus is small, this needs
    no extra dependency, and the scoring is inspectable. At a corpus size where
    rebuilding stops being instant, move it to Qdrant's sparse vectors - the
    retrieval interface above it would not change.
    """

    def __init__(self) -> None:
        self.documents: list[dict] = []
        self.term_frequencies: list[Counter] = []
        self.document_frequency: Counter = Counter()
        self.lengths: list[int] = []
        self.average_length: float = 0.0

    def build(self) -> "BM25Index":
        self.__init__()

        if not CHUNKS_DIR.exists():
            return self

        for chunk_file in sorted(CHUNKS_DIR.glob("*.json")):
            try:
                records = json.loads(chunk_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            for record in records:
                tokens = tokenize(record["text"])
                if not tokens:
                    continue

                self.documents.append(record)
                counts = Counter(tokens)
                self.term_frequencies.append(counts)
                self.lengths.append(len(tokens))
                # Document frequency counts documents, not occurrences.
                self.document_frequency.update(counts.keys())

        if self.lengths:
            self.average_length = sum(self.lengths) / len(self.lengths)
        return self

    def search(self, query: str, limit: int = 10) -> list[dict]:
        if not self.documents:
            return []

        query_terms = tokenize(query)
        if not query_terms:
            return []

        total = len(self.documents)
        scores: list[float] = [0.0] * total

        for term in query_terms:
            appears_in = self.document_frequency.get(term, 0)
            if appears_in == 0:
                continue

            # Smoothed IDF: rare terms count for more, and the +1 keeps the log
            # positive even for a term present in every document.
            idf = math.log(1 + (total - appears_in + 0.5) / (appears_in + 0.5))

            for index, counts in enumerate(self.term_frequencies):
                frequency = counts.get(term)
                if not frequency:
                    continue

                length_norm = 1 - B + B * (self.lengths[index] / self.average_length)
                scores[index] += idf * (
                    frequency * (K1 + 1) / (frequency + K1 * length_norm)
                )

        ranked = sorted(
            (i for i in range(total) if scores[i] > 0),
            key=lambda i: scores[i],
            reverse=True,
        )[:limit]

        return [{**self.documents[i], "score": scores[i]} for i in ranked]


_index: BM25Index | None = None
_lock = threading.Lock()


def get_index() -> BM25Index:
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                _index = BM25Index().build()
    return _index


def invalidate() -> None:
    """Drop the index so the next search rebuilds it.

    Called after a document is indexed or deleted. Rebuilding is cheap at this
    corpus size and avoids the class of bug where search silently serves stale
    results after an upload.
    """
    global _index
    with _lock:
        _index = None
