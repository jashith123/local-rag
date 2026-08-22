import os
from pathlib import Path

from dotenv import load_dotenv

# BASE_DIR is the "backend" folder.
# config.py -> core -> app -> backend
BASE_DIR = Path(__file__).resolve().parents[2]

# Read backend/.env so secrets stay out of the shell profile and out of git.
# Real environment variables win over the file.
load_dotenv(BASE_DIR / ".env", override=False)

STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIRECTORY = STORAGE_DIR / "uploads"

# Where document metadata lives until we move it into PostgreSQL.
DOCUMENT_DB_FILE = STORAGE_DIR / "documents.json"

# Extracted chunks, one JSON file per document. This is the handoff point:
# the embedding step will read from here and write vectors into Qdrant.
CHUNKS_DIR = STORAGE_DIR / "chunks"

# Only PDFs for now.
ALLOWED_CONTENT_TYPES = {"application/pdf"}
ALLOWED_EXTENSIONS = {".pdf"}

# 25 MB. Reject anything bigger before it fills the disk.
MAX_UPLOAD_SIZE = 25 * 1024 * 1024

# Chunking. CHUNK_OVERLAP repeats the tail of each chunk at the start of the
# next one so a sentence split across a boundary still appears intact somewhere.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# --- Embeddings -----------------------------------------------------------
# Runs locally on the CPU. Downloaded once to the HuggingFace cache (~90 MB),
# then loaded from disk. No API key, no per-request cost.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Must match the model. all-MiniLM-L6-v2 produces 384 floats per chunk.
# Changing the model almost always changes this, which means rebuilding the
# Qdrant collection and re-embedding every document.
EMBEDDING_DIMENSIONS = 384

# --- Vector database ------------------------------------------------------
# Set QDRANT_URL (e.g. "http://localhost:6333") to talk to a Qdrant server -
# see docker/docker-compose.yml. Left unset, qdrant-client runs embedded and
# stores vectors in this folder, which needs no Docker.
QDRANT_URL = os.environ.get("QDRANT_URL") or None
QDRANT_PATH = STORAGE_DIR / "qdrant"

QDRANT_COLLECTION = "documents"

# --- Retrieval ------------------------------------------------------------
# "hybrid"  vector + BM25 fused by reciprocal rank (default)
# "vector"  embeddings only — what this used to do
# "keyword" BM25 only
RETRIEVAL_MODE = os.environ.get("RETRIEVAL_MODE", "hybrid").strip().lower()

# Reciprocal rank fusion constant. 60 is the value from the original paper and
# the usual default; larger flattens the influence of top ranks.
RRF_K = 60

# Reranking. A cross-encoder re-scores the shortlist that retrieval produced.
# Costs a few hundred ms on CPU, so it is opt-out rather than always-on.
RERANK_ENABLED = os.environ.get("RERANK_ENABLED", "true").strip().lower() in {
    "1", "true", "yes"
}

# ~80 MB, downloaded once. Trained on MS MARCO query/passage relevance.
RERANK_MODEL = os.environ.get(
    "RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

# How many candidates to hand the reranker. Too few and it has nothing to fix;
# too many and it gets slow for no gain.
RERANK_CANDIDATES = int(os.environ.get("RERANK_CANDIDATES", "20"))

# --- Chat / answer generation ---------------------------------------------
# "ollama" runs a local model: free, offline, no key. "anthropic" calls the
# Claude API and needs ANTHROPIC_API_KEY.
CHAT_PROVIDER = os.environ.get("CHAT_PROVIDER", "ollama").strip().lower()

# Ollama. qwen3:4b-instruct measured best on this project's own prompt: same
# speed as qwen2.5:3b, fuller answers, and it declines an unanswerable question
# without inventing a citation, which qwen2.5:3b does.
#
# Deliberately the *instruct* tag, not plain qwen3:4b. The thinking variants
# reason before every answer - 2.5-9k characters of it - which made them 6-20x
# slower for no gain on a task that is "read five passages and cite them".
# Neither `think: false` nor a `/no_think` suffix suppressed it.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct")

# Five retrieved passages plus the system prompt run to roughly 2k tokens.
# Ollama's default context would quietly truncate that, which reads as the
# model ignoring the documents.
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))

# Anthropic.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or None

CHAT_MODEL = "claude-haiku-4-5"

# Answers are grounded summaries of a few retrieved passages, not essays.
# Deliberately modest: it bounds cost and keeps replies tight.
CHAT_MAX_TOKENS = 2048

# How many chunks to retrieve and hand to the model as context.
CHAT_TOP_K = 5

# Relevance gate on the reranker's score. Measured on this corpus, a passage
# that answers the question scores around +1 while unrelated ones land near
# -9; anything below this is not worth putting in front of the model.
#
# This is what stops a refusal carrying citations: rather than asking the model
# to answer from five irrelevant passages and hoping it declines cleanly, the
# question is answered as unanswerable without a model call at all.
CHAT_MIN_RERANK_SCORE = float(os.environ.get("CHAT_MIN_RERANK_SCORE", "-5.0"))
