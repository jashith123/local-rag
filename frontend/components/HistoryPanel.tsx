"use client";

import { relativeTime, type HistoryEntry } from "@/lib/history";

export function HistoryPanel({
  entries,
  activeQuery,
  onPick,
  onRemove,
  onClear,
  label = "Recent",
}: {
  entries: HistoryEntry[];
  activeQuery?: string;
  onPick: (query: string) => void;
  onRemove: (id: string) => void;
  onClear: () => void;
  label?: string;
}) {
  if (entries.length === 0) return null;

  return (
    <section aria-label={label}>
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
          {label}
        </h2>
        <button
          type="button"
          onClick={onClear}
          className="text-xs text-zinc-500 transition-colors hover:text-zinc-900 dark:hover:text-zinc-100"
        >
          Clear all
        </button>
      </div>

      <ul className="flex flex-wrap gap-2">
        {entries.map((entry) => {
          const active =
            activeQuery?.trim().toLowerCase() === entry.query.toLowerCase();

          return (
            <li key={entry.id}>
              {/* Not a <button> wrapping a <button> — nesting them is invalid
                  HTML and the inner click never reaches the remove handler. */}
              <div
                className={`group flex items-center rounded-full text-xs ring-1 transition-colors ${
                  active
                    ? "bg-zinc-900 text-white ring-zinc-900 dark:bg-zinc-100 dark:text-zinc-900 dark:ring-zinc-100"
                    : "bg-white ring-zinc-200 hover:bg-zinc-100 dark:bg-zinc-900 dark:ring-zinc-800 dark:hover:bg-zinc-800"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onPick(entry.query)}
                  title={`${entry.query}${entry.meta ? ` — ${entry.meta}` : ""} · ${relativeTime(entry.at)}`}
                  className="max-w-64 truncate py-1.5 pl-3 pr-1.5 text-left"
                >
                  {entry.query}
                  {entry.meta && (
                    <span
                      className={
                        active
                          ? "ml-2 opacity-70"
                          : "ml-2 text-zinc-400 dark:text-zinc-500"
                      }
                    >
                      {entry.meta}
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => onRemove(entry.id)}
                  aria-label={`Remove "${entry.query}" from history`}
                  className="mr-1 grid h-5 w-5 shrink-0 place-items-center rounded-full opacity-40 transition-opacity hover:opacity-100"
                >
                  <svg viewBox="0 0 24 24" className="h-3 w-3" aria-hidden>
                    <path
                      d="M6 6l12 12M18 6L6 18"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
