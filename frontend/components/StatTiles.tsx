import type { DocumentMetadata } from "@/lib/api";

// These are headline counts, not a chart — a stat tile is the right form for a
// single number, and adding a plot here would carry no extra information.
// The number wears text tokens; no series colour is involved.
function Tile({
  label,
  value,
  hint,
  loading,
}: {
  label: string;
  value: number | null;
  hint: string;
  loading: boolean;
}) {
  return (
    <div className="rounded-xl bg-white p-4 ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800">
      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">
        {label}
      </div>
      {loading ? (
        <div className="skeleton mt-2 h-8 w-16 rounded-md bg-zinc-200 dark:bg-zinc-800" />
      ) : (
        <div className="mt-1 text-3xl font-semibold tabular-nums tracking-tight">
          {value ?? "—"}
        </div>
      )}
      <div className="mt-1 text-xs text-zinc-500">{hint}</div>
    </div>
  );
}

function sum(
  documents: DocumentMetadata[],
  pick: (d: DocumentMetadata) => number | null,
) {
  return documents.reduce((total, doc) => total + (pick(doc) ?? 0), 0);
}

export function StatTiles({
  documents,
  indexedChunks,
  loading,
}: {
  documents: DocumentMetadata[];
  indexedChunks: number | null;
  loading: boolean;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Tile
        label="Documents"
        value={loading ? null : documents.length}
        hint="PDFs uploaded"
        loading={loading}
      />
      <Tile
        label="Pages"
        value={loading ? null : sum(documents, (d) => d.page_count)}
        hint="text extracted"
        loading={loading}
      />
      <Tile
        label="Chunks"
        value={loading ? null : sum(documents, (d) => d.chunk_count)}
        hint="overlapping passages"
        loading={loading}
      />
      <Tile
        label="Vectors"
        value={loading ? null : indexedChunks}
        hint="searchable in Qdrant"
        loading={loading}
      />
    </div>
  );
}
