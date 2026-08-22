"use client";

import { useEffect, useState } from "react";
import { ApiError, documentChunks, type DocumentChunk } from "@/lib/api";

/**
 * The passages a document was actually split into.
 *
 * This is the only place you can see what the extractor produced rather than
 * what the PDF looks like to a human — which is usually the answer when
 * retrieval behaves oddly on a document that "obviously" contains the answer.
 */
export function ChunkViewer({
  documentId,
  filename,
}: {
  documentId: string;
  filename: string;
}) {
  const [chunks, setChunks] = useState<DocumentChunk[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const handle = setTimeout(async () => {
      try {
        const data = await documentChunks(documentId);
        if (!cancelled) setChunks(data.chunks);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "Could not load chunks.",
          );
        }
      }
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [documentId]);

  if (error) {
    return <p className="px-4 py-3 text-sm text-red-600 dark:text-red-400">{error}</p>;
  }

  if (chunks === null) {
    return (
      <div className="space-y-2 px-4 py-3">
        {[0, 1].map((i) => (
          <div
            key={i}
            className="skeleton h-12 rounded-lg bg-zinc-200 dark:bg-zinc-800"
          />
        ))}
      </div>
    );
  }

  if (chunks.length === 0) {
    return (
      <p className="px-4 py-3 text-sm text-zinc-500">
        No chunks — extraction produced no text. If this is a scanned PDF it
        needs OCR, which isn&apos;t wired up yet.
      </p>
    );
  }

  return (
    <div className="space-y-2 px-4 py-3">
      <div className="flex items-center justify-between text-xs text-zinc-500">
        <span>
          {chunks.length} chunk{chunks.length === 1 ? "" : "s"} — this is the
          text that was embedded
        </span>
        <a
          href={`/api/documents/${documentId}/file`}
          target="_blank"
          rel="noreferrer"
          className="underline decoration-dotted underline-offset-2 transition-colors hover:text-zinc-900 dark:hover:text-zinc-100"
        >
          Open {filename}
        </a>
      </div>

      <ol className="space-y-2">
        {chunks.map((chunk) => (
          <li
            key={chunk.chunk_index}
            className="rounded-lg bg-zinc-50 p-3 ring-1 ring-zinc-200 dark:bg-zinc-950 dark:ring-zinc-800"
          >
            <div className="mb-1 flex items-center gap-2 text-xs text-zinc-500">
              <span className="font-medium">#{chunk.chunk_index}</span>
              {chunk.page && (
                <a
                  href={`/api/documents/${documentId}/file#page=${chunk.page}`}
                  target="_blank"
                  rel="noreferrer"
                  className="underline decoration-dotted underline-offset-2 hover:text-zinc-900 dark:hover:text-zinc-100"
                >
                  page {chunk.page}
                </a>
              )}
              <span className="ml-auto tabular-nums">
                {chunk.text.length} chars
              </span>
            </div>
            <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
              {chunk.text}
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}
