import threading
import uuid
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams
)

from app.core.config import (
    EMBEDDING_DIMENSIONS,
    QDRANT_COLLECTION,
    QDRANT_PATH,
    QDRANT_URL
)

# Qdrant point IDs must be an unsigned integer or a UUID - it will not accept
# "<document_id>:3". uuid5 hashes that string into a valid UUID deterministically,
# so re-indexing the same chunk overwrites its point instead of duplicating it.
_POINT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

_client = None
_lock = threading.Lock()


def _point_id(document_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(_POINT_NAMESPACE, f"{document_id}:{chunk_index}"))


def _ensure_collection(client: QdrantClient) -> None:
    if client.collection_exists(QDRANT_COLLECTION):
        existing = client.get_collection(QDRANT_COLLECTION)
        size = existing.config.params.vectors.size
        if size != EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                f"Collection '{QDRANT_COLLECTION}' stores {size}-dim vectors but "
                f"the configured model produces {EMBEDDING_DIMENSIONS}. Delete the "
                f"collection and re-index, or switch back to the previous model."
            )
        return

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        # Cosine, because the embedder normalizes its vectors - with unit-length
        # vectors, cosine similarity is the meaningful comparison.
        vectors_config=VectorParams(
            size=EMBEDDING_DIMENSIONS,
            distance=Distance.COSINE
        )
    )


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                if QDRANT_URL:
                    client = QdrantClient(url=QDRANT_URL)
                else:
                    # Embedded mode: no server, no Docker. Qdrant keeps an
                    # exclusive lock on this folder, so only one process can
                    # hold it at a time.
                    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
                    client = QdrantClient(path=str(QDRANT_PATH))
                _ensure_collection(client)
                _client = client
    return _client


def index_chunks(
    document_id: str,
    original_filename: str,
    records: list[dict],
    vectors: list[list[float]]
) -> int:
    """Store one point per chunk: the vector plus enough payload to cite it."""
    if not records:
        return 0

    points = [
        PointStruct(
            id=_point_id(document_id, index),
            vector=vector,
            payload={
                "document_id": document_id,
                "original_filename": original_filename,
                "chunk_index": index,
                # The page makes a result citable as "page 4" rather than the
                # meaningless-to-a-reader "chunk 7".
                "page": record["page"],
                # The text rides along with the vector so a search result can be
                # shown to the user without a second lookup on disk.
                "text": record["text"]
            }
        )
        for index, (record, vector) in enumerate(zip(records, vectors))
    ]

    get_client().upsert(collection_name=QDRANT_COLLECTION, points=points)
    return len(points)


def search(
    vector: list[float],
    limit: int = 5,
    document_id: Optional[str] = None
) -> list[dict]:
    query_filter = None
    if document_id:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id)
                )
            ]
        )

    response = get_client().query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        limit=limit,
        query_filter=query_filter,
        with_payload=True
    )

    return [
        {
            "score": point.score,
            "document_id": point.payload["document_id"],
            "original_filename": point.payload["original_filename"],
            "chunk_index": point.payload["chunk_index"],
            # Documents indexed before page tracking existed have no page.
            "page": point.payload.get("page"),
            "text": point.payload["text"]
        }
        for point in response.points
    ]


def delete_document(document_id: str) -> None:
    get_client().delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id)
                )
            ]
        )
    )


def count() -> int:
    return get_client().count(collection_name=QDRANT_COLLECTION).count
