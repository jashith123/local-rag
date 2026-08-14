"""Compare retrieval modes against the golden set.

    cd backend
    .venv/Scripts/python.exe ../scripts/evaluate.py

The API server must be stopped first — embedded Qdrant allows one process at a
time. Add --mode to test a single mode instead of all three.
"""
import argparse
import sys
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
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not corpus_is_indexed():
        print("No chunks indexed. Upload a document first.")
        return 1

    cases = load_golden(GOLDEN)
    modes = [args.mode] if args.mode else ["vector", "keyword", "hybrid"]

    print(f"{len(cases)} golden questions, k={args.k}\n")
    header = f"{'mode':<9} {'recall@1':>9} {'recall@3':>9} {'recall@5':>9} {'MRR':>7}"
    print(header)
    print("-" * len(header))

    results = {}
    for mode in modes:
        result = evaluate(cases, mode=mode, k=args.k)
        results[mode] = result
        print(
            f"{mode:<9} {result.recall_at_1:>9.0%} {result.recall_at_3:>9.0%} "
            f"{result.recall_at_5:>9.0%} {result.mrr:>7.3f}"
        )

    if "vector" in results and "hybrid" in results:
        base, hybrid = results["vector"], results["hybrid"]
        delta_recall = hybrid.recall_at_5 - base.recall_at_5
        delta_mrr = hybrid.mrr - base.mrr
        print(
            f"\nhybrid vs vector:  recall@5 {delta_recall:+.0%}  "
            f"MRR {delta_mrr:+.3f}"
        )

    for mode, result in results.items():
        if result.misses:
            print(f"\n{mode} missed ({len(result.misses)}):")
            for question in result.misses:
                print(f"  - {question}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
