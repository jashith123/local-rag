import type { DocumentStatus } from "@/lib/api";

// Status colours are reserved for state and never reused as decoration. Each
// one ships with its text label, so the state is never carried by colour alone.
const STYLES: Record<DocumentStatus, string> = {
  uploaded:
    "bg-zinc-100 text-zinc-700 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:ring-zinc-700",
  processing:
    "bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30",
  processed:
    "bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30",
  failed:
    "bg-red-50 text-red-800 ring-red-200 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/30",
};

const LABELS: Record<DocumentStatus, string> = {
  uploaded: "queued",
  processing: "processing",
  processed: "indexed",
  failed: "failed",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  const busy = status === "uploaded" || status === "processing";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${STYLES[status]}`}
    >
      {busy ? (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-70" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
        </span>
      ) : (
        <span className="h-1.5 w-1.5 rounded-full bg-current" />
      )}
      {LABELS[status]}
    </span>
  );
}
