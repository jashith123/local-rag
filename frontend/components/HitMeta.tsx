import type { SearchHit } from "@/lib/api";

/**
 * The provenance line for a retrieved passage: where it came from, and which
 * retriever found it.
 *
 * The score shown is deliberately NOT `hit.score`. In hybrid mode that is a
 * fused reciprocal-rank value of about 0.03 — fine for ordering, meaningless
 * to a reader, and on a completely different scale from the cosine similarity
 * the UI used to display. Showing the per-retriever score keeps the number
 * interpretable.
 */
export function HitMeta({
  hit,
  rank,
}: {
  hit: SearchHit;
  rank?: number;
}) {
  const bySemantic = hit.matched_by.includes("vector");
  const byKeyword = hit.matched_by.includes("keyword");
  const byBoth = bySemantic && byKeyword;

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {rank !== undefined && (
        <span className="grid h-5 w-5 place-items-center rounded bg-zinc-100 font-medium tabular-nums text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
          {rank}
        </span>
      )}
      <span className="font-medium">{hit.original_filename}</span>
      <span className="text-zinc-500">
        {hit.page ? `page ${hit.page}` : `chunk ${hit.chunk_index}`}
      </span>

      <span className="ml-auto flex items-center gap-1.5">
        {/* Both retrievers agreeing is the strongest signal available, so it
            gets its own label rather than two neutral chips. */}
        {byBoth ? (
          <span className="rounded-md bg-emerald-50 px-1.5 py-0.5 font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
            semantic + keyword
          </span>
        ) : (
          <>
            {bySemantic && (
              <span className="rounded-md bg-zinc-100 px-1.5 py-0.5 font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                semantic
              </span>
            )}
            {byKeyword && (
              <span className="rounded-md bg-zinc-100 px-1.5 py-0.5 font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                keyword
              </span>
            )}
          </>
        )}

        {hit.vector_score !== null && (
          <span
            className="tabular-nums text-zinc-500"
            title="Cosine similarity from the embedding model"
          >
            {hit.vector_score.toFixed(3)}
          </span>
        )}
      </span>
    </div>
  );
}
