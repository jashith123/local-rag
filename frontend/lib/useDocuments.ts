"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  listDocuments,
  searchStats,
  type DocumentMetadata,
} from "./api";

const POLL_MS = 1500;

export function isPending(doc: DocumentMetadata) {
  return doc.status === "uploaded" || doc.status === "processing";
}

/**
 * Owns the document list and the Qdrant count, and keeps them fresh while any
 * document is still being processed.
 *
 * One hook rather than per-component fetching: the stat tiles and the table
 * show the same data, and two independent pollers would double the requests and
 * let the two views disagree for a moment.
 */
export function useDocuments(refreshToken: number) {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [indexedChunks, setIndexedChunks] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let handle: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const [docs, stats] = await Promise.all([
          listDocuments(),
          searchStats(),
        ]);
        if (cancelled) return;

        setDocuments(docs.documents);
        setIndexedChunks(stats.indexed_chunks);
        setError(null);

        // Extraction and embedding run in a background task, so statuses change
        // after the upload response. Chain the next poll off this response so a
        // slow request can't stack, and stop once nothing is in flight.
        if (docs.documents.some(isPending)) {
          handle = setTimeout(poll, POLL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError ? err.message : "Could not load documents.",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    // Even the first fetch goes through a timer: React treats a setState made
    // synchronously in an effect body as a cascading render.
    handle = setTimeout(poll, 0);

    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [refreshToken]);

  return { documents, indexedChunks, loading, error };
}
