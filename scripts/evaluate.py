"""Compare retrieval configurations against the golden set.

    cd backend
    .venv/Scripts/python.exe ../scripts/evaluate.py

The API server must be stopped first — embedded Qdrant allows one process at a
time. Use --mode / --no-rerank to test a single configuration.
"""
import argparse
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.rag.evaluation import (  # noqa: E402
    corpus_is_indexed,
    evaluate,
    load_golden,
)

GOLDEN = BACKEND / "eval" / "golden.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["hybrid", "vector", "keyword"])
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--no-rerank", action="store_true", help="skip the reranked variants"
    )
    args = parser.parse_args()

    if not corpus_is_indexed():
        print("No chunks indexed. Upload a document first.")
        return 1

    cases = load_golden(GOLDEN)
    modes = [args.mode] if args.mode else ["vector", "keyword", "hybrid"]

    # Each configuration is (label, mode, rerank).
    configs = [(mode, mode, False) for mode in modes]
    if not args.no_rerank:
        configs += [(f"{mode} + rerank", mode, True) for mode in modes]

    print(f"{len(cases)} golden questions, k={args.k}\n")
    header = (
        f"{'config':<18} {'recall@1':>9} {'recall@3':>9} {'recall@5':>9} "
        f"{'MRR':>7} {'sec/q':>7}"
    )
    print(header)
    print("-" * len(header))

    results = {}
    for label, mode, rerank in configs:
        started = time.time()
        result = evaluate(cases, mode=mode, k=args.k, rerank=rerank)
        per_query = (time.time() - started) / max(len(cases), 1)
        results[label] = result
        print(
            f"{label:<18} {result.recall_at_1:>9.0%} {result.recall_at_3:>9.0%} "
            f"{result.recall_at_5:>9.0%} {result.mrr:>7.3f} {per_query:>7.2f}"
        )

    def delta(a: str, b: str) -> None:
        if a in results and b in results:
            first, second = results[a], results[b]
            print(
                f"\n{b} vs {a}:  recall@5 "
                f"{second.recall_at_5 - first.recall_at_5:+.0%}  "
                f"MRR {second.mrr - first.mrr:+.3f}"
            )

    delta("vector", "hybrid")
    delta("hybrid", "hybrid + rerank")

    for label, result in results.items():
        if result.misses:
            print(f"\n{label} missed ({len(result.misses)}):")
            for question in result.misses:
                print(f"  - {question}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
