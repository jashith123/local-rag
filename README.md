# local-rag

Ask questions about your own PDFs and get answers with citations back to the
page they came from. Everything runs on your machine: no API key, no cloud, no
document ever leaves the laptop.

Upload a PDF and it is extracted, split into overlapping passages, embedded and
indexed. Search it by meaning, or ask a question and get a grounded answer that
cites the passages it used.

```
PDF -> extract -> chunk -> embed -> Qdrant
                                      |
question -> rewrite -> [ vector + BM25 ] -> fuse -> rerank -> LLM -> answer + citations
```

## Why it is built this way

**Hybrid retrieval, not just embeddings.** Vector search alone missed a query
for "blood group" against a form that literally contains the words "Blood
Group" - that passage has a cosine similarity of 0.037, so a code listing
outranked it. BM25 catches exactly that case. The two rankings are merged with
reciprocal rank fusion, which uses only each retriever's *rank*, because cosine
(~0.3) and BM25 (~4.2) are not comparable numbers.

**A reranker decides the final order.** A cross-encoder reads the question
against each candidate passage rather than comparing two vectors computed
separately. On the same query it scored the right passage +0.96 and the rest
-8.55, -10.20, -10.81 - a separation cosine never produces.

**Measured, not assumed.** `scripts/evaluate.py` runs a golden set and reports
recall@k and MRR per configuration, so every retrieval change is a number
rather than an opinion:

```
config              recall@1  recall@3  recall@5     MRR   sec/q
vector                   88%       96%       96%   0.913    0.55
keyword                  84%       96%      100%   0.908    0.00
hybrid                   92%      100%      100%   0.947    0.01
hybrid + rerank         100%      100%      100%   1.000    0.73
```

Reranking does not find anything new here - recall@5 is 100% either way. It
fixes the *order*, at roughly 70x the retrieval latency.

## Running it

Requires Python 3.11+, Node 20+, and [Ollama](https://ollama.com) for answers.

```bash
# backend
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Linux/macOS: .venv/bin/pip
ollama pull qwen3:4b-instruct
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# frontend, in another terminal
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The API docs are at http://localhost:8000/docs.

First start downloads an embedding model (~90 MB) and a reranker (~80 MB), then
warms both, so the first search is not slow.

## Configuration

Everything works with no configuration. Copy `backend/.env.example` to
`backend/.env` to change any of it - model, retrieval mode, whether reranking
runs, or to use the Claude API instead of a local model.

## Tests and evaluation

```bash
cd backend
.venv/Scripts/python -m pytest                  # 41 unit tests, under a second
.venv/Scripts/python ../scripts/evaluate.py     # retrieval quality, server stopped
.venv/Scripts/python ../scripts/bench_models.py qwen3:4b-instruct qwen2.5:3b
```

`evaluate.py` and `reindex.py` need the API server stopped: embedded Qdrant
takes an exclusive lock on its storage folder.

## Stack

| | |
|---|---|
| API | FastAPI, streamed over SSE |
| Extraction | pypdf, chunked per page so citations carry a page number |
| Embeddings | sentence-transformers, `all-MiniLM-L6-v2`, local |
| Keyword | BM25, implemented in-process |
| Vectors | Qdrant, embedded by default (`docker/` has a server compose file) |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2`, local |
| Answers | Ollama (`qwen3:4b-instruct`) or the Claude API |
| Frontend | Next.js 16, React 19, Tailwind v4 |

## Known limits

- Metadata lives in a JSON file and Qdrant runs embedded, so this is
  single-process. `uvicorn --workers 2` will not work until both move to a
  server.
- Ingestion runs in a FastAPI background task, so a document being processed
  when the server stops is stuck at "processing" with no retry.
- Scanned PDFs extract as empty - there is no OCR.
- Conversations and search history are stored per browser, in localStorage.
