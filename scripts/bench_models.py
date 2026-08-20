"""Benchmark Ollama models on this project's actual RAG prompt.

    cd backend
    .venv/Scripts/python.exe ../scripts/bench_models.py

Stop the API server first — embedded Qdrant allows one process at a time.

Newer Qwen models reason before answering by default. That is wrong for this
job: the answer must be a short grounded paragraph with citations, not a
visible chain of thought. Each thinking-capable model is therefore measured
both ways.
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.rag.prompt import SYSTEM_PROMPT, build_user_message  # noqa: E402
from app.rag.retrieval import retrieve  # noqa: E402

OLLAMA = "http://localhost:11434/api/chat"

QUESTIONS = [
    "why do chunks need to overlap",
    "what is the time complexity of BFS",
    "what stops the algorithm looping forever on a cycle",
    "who won the 1998 world cup",  # unanswerable from these documents
]


def ask(model: str, system: str, user: str, think=None) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }
    if think is not None:
        payload["think"] = think

    request = urllib.request.Request(
        OLLAMA,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    started = time.time()
    with urllib.request.urlopen(request, timeout=900) as response:
        body = json.loads(response.read())

    message = body.get("message", {})
    return {
        "text": (message.get("content") or "").strip(),
        "thinking": (message.get("thinking") or "").strip(),
        "seconds": time.time() - started,
        "in": body.get("prompt_eval_count", 0),
        "out": body.get("eval_count", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="+")
    parser.add_argument("--full", action="store_true", help="print whole answers")
    args = parser.parse_args()

    # Retrieve once and reuse, so every model sees identical context.
    contexts = {}
    for question in QUESTIONS:
        hits = retrieve(query=question, limit=5, rerank=False)
        contexts[question] = (build_user_message(question, hits), len(hits))

    summary = {}

    for model in args.models:
        # Try with thinking explicitly off; fall back if the server rejects it.
        variants = [("think=off", False), ("default", None)]
        for label, think in variants:
            key = f"{model} [{label}]"
            totals = {"sec": 0.0, "out": 0, "cited": 0, "leaked": 0}
            print("=" * 78)
            print(key)
            print("=" * 78)

            failed = False
            for question in QUESTIONS:
                user, hit_count = contexts[question]
                try:
                    result = ask(model, SYSTEM_PROMPT, user, think=think)
                except Exception as exc:
                    print(f"  FAILED: {exc}")
                    failed = True
                    break

                text = result["text"]
                cited = any(f"[{i}]" in text for i in range(1, 6))
                leaked = "<think" in text.lower() or "</think" in text.lower()

                totals["sec"] += result["seconds"]
                totals["out"] += result["out"]
                totals["cited"] += int(cited)
                totals["leaked"] += int(leaked)

                print(f"\n  Q: {question}   ({hit_count} passages)")
                print(
                    f"     {result['seconds']:.1f}s  {result['out']} out"
                    f"  cites={cited}  leaked_tags={leaked}"
                    + (f"  thinking={len(result['thinking'])}ch"
                       if result["thinking"] else "")
                )
                shown = text if args.full else text[:260]
                print("     " + shown.replace("\n", "\n     "))

            if not failed:
                summary[key] = totals
            print()

    print("=" * 78)
    print(f"{'config':<34} {'total s':>8} {'out tok':>8} {'cited':>7} {'leaked':>7}")
    print("-" * 78)
    for key, totals in summary.items():
        print(
            f"{key:<34} {totals['sec']:>8.1f} {totals['out']:>8} "
            f"{totals['cited']:>5}/{len(QUESTIONS)} {totals['leaked']:>7}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
