"use client";

import { useState } from "react";
import { ApiError, deleteDocument, formatBytes, type DocumentMetadata } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";

function SkeletonRows() {
  return (
    <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-4">
          <div className="flex-1 space-y-2">
            <div className="skeleton h-3.5 w-48 rounded bg-zinc-200 dark:bg-zinc-800" />
            <div className="skeleton h-2.5 w-24 rounded bg-zinc-200 dark:bg-zinc-800" />
          </div>
          <div className="skeleton h-6 w-20 rounded-full bg-zinc-200 dark:bg-zinc-800" />
          <div className="skeleton h-3.5 w-32 rounded bg-zinc-200 dark:bg-zinc-800" />
        </div>
      ))}
    </div>
  );
}

function Cell({ value }: { value: number | null }) {
  return (
    <td className="px-4 py-3 text-right tabular-nums">
      {value ?? <span className="text-zinc-400 dark:text-zinc-600">—</span>}
    </td>
  );
}

export function DocumentList({
  documents,
  loading,
  error,
  onDeleted,
}: {
  documents: DocumentMetadata[];
  loading: boolean;
  error: string | null;
  onDeleted?: () => void;
}) {
  const [deleting, setDeleting] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function remove(doc: DocumentMetadata) {
    // Deleting removes the PDF, its chunks and its vectors — not undoable, so
    // it gets a confirmation rather than a bare icon click.
    if (
      !window.confirm(
        `Delete "${doc.original_filename}"?\n\nThis removes the file, its text chunks and its vectors. It cannot be undone.`,
      )
    ) {
      return;
    }

    setDeleting(doc.document_id);
    setDeleteError(null);
    try {
      await deleteDocument(doc.document_id);
      onDeleted?.();
    } catch (err) {
      setDeleteError(
        err instanceof ApiError ? err.message : "Could not delete the document.",
      );
    } finally {
      setDeleting(null);
    }
  }

  if (loading) {
    return (
      <div className="overflow-hidden rounded-xl bg-white ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800">
        <SkeletonRows />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/30">
        {error}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-300 px-6 py-12 text-center dark:border-zinc-700">
        <p className="text-sm font-medium">No documents yet</p>
        <p className="mt-1 text-sm text-zinc-500">
          Upload a PDF above and it will be extracted, chunked, embedded and
          indexed automatically.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl bg-white ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800">
      <table className="w-full text-sm">
        <thead className="border-b border-zinc-200 text-left text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
          <tr>
            <th className="px-4 py-3 font-medium">File</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 text-right font-medium">Pages</th>
            <th className="px-4 py-3 text-right font-medium">Chunks</th>
            <th className="px-4 py-3 text-right font-medium">Vectors</th>
            <th className="px-4 py-3 text-right font-medium">Size</th>
            <th className="w-10 px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {documents.map((doc) => (
            <tr
              key={doc.document_id}
              className="transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
            >
              <td className="px-4 py-3">
                <div className="flex items-start gap-3">
                  <svg
                    viewBox="0 0 24 24"
                    className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400"
                    aria-hidden
                  >
                    <path
                      d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.75"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M14 2v6h6"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.75"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <div className="min-w-0">
                    <div className="truncate font-medium">
                      {doc.original_filename}
                    </div>
                    <div className="font-mono text-xs text-zinc-500">
                      {doc.document_id.slice(0, 8)}
                    </div>
                    {doc.error && (
                      <div className="mt-1 text-xs text-red-600 dark:text-red-400">
                        {doc.error}
                      </div>
                    )}
                  </div>
                </div>
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={doc.status} />
              </td>
              <Cell value={doc.page_count} />
              <Cell value={doc.chunk_count} />
              <Cell value={doc.vector_count} />
              <td className="px-4 py-3 text-right tabular-nums text-zinc-500">
                {formatBytes(doc.size)}
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  type="button"
                  onClick={() => void remove(doc)}
                  disabled={deleting === doc.document_id}
                  aria-label={`Delete ${doc.original_filename}`}
                  title="Delete document"
                  className="grid h-7 w-7 place-items-center rounded-lg text-zinc-400 transition-colors hover:bg-red-50 hover:text-red-600 disabled:opacity-40 dark:hover:bg-red-500/10 dark:hover:text-red-400"
                >
                  {deleting === doc.document_id ? (
                    <span className="h-3 w-3 animate-pulse rounded-full bg-current" />
                  ) : (
                    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
                      <path
                        d="M4 7h16M10 11v6M14 11v6M5 7l1 13a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1l1-13M9 7V4h6v3"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.75"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {deleteError && (
        <p className="border-t border-zinc-200 px-4 py-2 text-sm text-red-600 dark:border-zinc-800 dark:text-red-400">
          {deleteError}
        </p>
      )}
    </div>
  );
}
