"""Retrieval evaluation.

Without this, "hybrid search improved things" is an opinion. A golden set of
question -> expected-passage pairs turns every retrieval change into a number
you can compare before and after.

Two metrics, because they answer different questions:

  recall@k  did the right passage appear in the top k at all?
            (what matters for RAG - the model only sees the top k)
  MRR       how high up was it?
            (1.0 = always first, 0.5 = typically second)
"""
import json
from dataclasses import dataclass
from typing import Callable, Optional

from app.core.config import CHUNKS_DIR
from app.rag.retrieval import Mode, retrieve


@dataclass
class GoldenCase:
    question: str
    #: Substring that must appear in the retrieved passage for it to count.
    #: Substring rather than chunk id, so the golden set survives re-chunking.
    expect_text: str
    #: Optionally require the hit to come from a particular file.
    expect_file: Optional[str] = None


@dataclass
class Result:
    mode: str
    cases: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    misses: list[str]


def _matches(hit: dict, case: GoldenCase) -> bool:
    if case.expect_file and case.expect_file.lower() not in hit["original_filename"].lower():
        return False
    haystack = " ".join(hit["text"].split()).lower()
    return case.expect_text.lower() in haystack


def evaluate(
    cases: list[GoldenCase],
    mode: Mode = "hybrid",
    k: int = 5,
    rerank: Optional[bool] = None,
    retriever: Optional[Callable[..., list[dict]]] = None,
) -> Result:
    retriever = retriever or retrieve

    hits_at = {1: 0, 3: 0, 5: 0}
    reciprocal_ranks: list[float] = []
    misses: list[str] = []

    for case in cases:
        results = retriever(query=case.question, limit=k, mode=mode, rerank=rerank)

        rank = next(
            (i for i, hit in enumerate(results, start=1) if _matches(hit, case)),
            None,
        )

        if rank is None:
            reciprocal_ranks.append(0.0)
            misses.append(case.question)
            continue

        reciprocal_ranks.append(1.0 / rank)
        for threshold in hits_at:
            if rank <= threshold:
                hits_at[threshold] += 1

    total = len(cases) or 1
    return Result(
        mode=mode,
        cases=len(cases),
        recall_at_1=hits_at[1] / total,
        recall_at_3=hits_at[3] / total,
        recall_at_5=hits_at[5] / total,
        mrr=sum(reciprocal_ranks) / total,
        misses=misses,
    )


def load_golden(path) -> list[GoldenCase]:
    """Load the golden set, ignoring any `_`-prefixed annotation keys.

    The file is meant to be edited by hand, so it should tolerate a `_comment`
    sitting next to a real case without blowing up the loader.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        GoldenCase(
            **{key: value for key, value in case.items() if not key.startswith("_")}
        )
        for case in data
    ]


def corpus_is_indexed() -> bool:
    return CHUNKS_DIR.exists() and any(CHUNKS_DIR.glob("*.json"))
