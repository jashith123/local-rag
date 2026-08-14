"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  listDocuments,
  search,
  searchStats,
  type DocumentMetadata,
  type SearchResponse,
} from "@/lib/api";
import { useHistory } from "@/lib/history";
import { HistoryPanel } from "./HistoryPanel";
import { HitMeta } from "./HitMeta";
import { Suggestions } from "./Suggestions";

export function SearchPanel() {
  const router = useRouter();
  const params = useSearchParams();

  // The URL is the source of truth for what has been searched. That makes
  // browser back/forward step through past searches, makes a result set
  // reloadable, and makes it a link you can send someone.
  const query = params.get("q") ?? "";
  const limit = Number(params.get("limit") ?? 5);
  const documentId = params.get("doc") ?? "";

  const [draft, setDraft] = useState(query);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [indexed, setIndexed] = useState<number | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const { entries, add, remove, clear } = useHistory("search");

  // Shell-style recall: ArrowUp walks back through history, ArrowDown returns.
  const [recallIndex, setRecallIndex] = useState(-1);
  const draftBeforeRecall = useRef("");

  useEffect(() => {
    listDocuments()
      .then((data) =>
        setDocuments(data.documents.filter((d) => d.status === "processed")),
      )
      .catch(() => undefined);
    searchStats()
      .then((s) => setIndexed(s.indexed_chunks))
      .catch(() => undefined);
  }, []);

  // "/" focuses the search box, the convention in every search-first tool.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const typing =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "SELECT";
      if (e.key === "/" && !typing) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Run whenever the URL changes — from a submit, a history chip, or the
  // browser's own back/forward buttons. One code path for all three.
  useEffect(() => {
    let cancelled = false;

    const handle = setTimeout(async () => {
      setDraft(query);
      setRecallIndex(-1);

      if (!query.trim()) {
        setResponse(null);
        setError(null);
        setElapsed(null);
        return;
      }

      setBusy(true);
      setError(null);
      const started = performance.now();

      try {
        const result = await search(query, limit, documentId || undefined);
        if (cancelled) return;
        setResponse(result);
        setElapsed(performance.now() - started);

        const best = result.results[0]?.score;
        add(
          query,
          `${result.count} hit${result.count === 1 ? "" : "s"}${
            best !== undefined ? ` · ${best.toFixed(2)}` : ""
          }`,
        );
      } catch (err) {
        if (cancelled) return;
        setResponse(null);
        setElapsed(null);
        setError(err instanceof ApiError ? err.message : "Search failed.");
      } finally {
        if (!cancelled) setBusy(false);
      }
    }, 0);

    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
    // `add` is stable (useCallback on a module-level store).
  }, [query, limit, documentId, add]);

  /** Navigate to a search. Pushing a new entry is what makes Back work. */
  function go(next: {
    q?: string;
    limit?: number;
    doc?: string;
    replace?: boolean;
  }) {
    const q = (next.q ?? query).trim();
    const search = new URLSearchParams();
    if (q) search.set("q", q);
    const nextLimit = next.limit ?? limit;
    if (nextLimit !== 5) search.set("limit", String(nextLimit));
    const nextDoc = next.doc ?? documentId;
    if (nextDoc) search.set("doc", nextDoc);

    const url = `/search${search.toString() ? `?${search}` : ""}`;
    if (next.replace) router.replace(url);
    else router.push(url);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") {
      setDraft("");
      setRecallIndex(-1);
      return;
    }

    if (e.key === "ArrowUp") {
      if (entries.length === 0) return;
      e.preventDefault();
      if (recallIndex === -1) draftBeforeRecall.current = draft;
      const next = Math.min(recallIndex + 1, entries.length - 1);
      setRecallIndex(next);
      setDraft(entries[next].query);
      return;
    }

    if (e.key === "ArrowDown") {
      if (recallIndex < 0) return;
      e.preventDefault();
      const next = recallIndex - 1;
      setRecallIndex(next);
      setDraft(next === -1 ? draftBeforeRecall.current : entries[next].query);
    }
  }

  return (
    <div className="space-y-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (draft.trim()) go({ q: draft });
        }}
        className="space-y-3"
      >
        <div className="flex gap-2">
          <div className="relative flex-1">
            <svg
              viewBox="0 0 24 24"
              className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400"
              aria-hidden
            >
              <circle
                cx="11"
                cy="11"
                r="7"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              />
              <path
                d="m16.5 16.5 4 4"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                setRecallIndex(-1);
              }}
              onKeyDown={onKeyDown}
              placeholder="Ask in plain language…"
              aria-label="Search query"
              className="w-full rounded-xl bg-white py-2.5 pl-10 pr-20 text-sm shadow-sm outline-none ring-1 ring-zinc-200 transition-shadow placeholder:text-zinc-400 focus:ring-2 focus:ring-zinc-900 dark:bg-zinc-900 dark:ring-zinc-800 dark:focus:ring-zinc-100"
            />
            <div className="absolute right-2.5 top-1/2 flex -translate-y-1/2 items-center gap-1">
              {draft && (
                <button
                  type="button"
                  onClick={() => {
                    setDraft("");
                    setRecallIndex(-1);
                    inputRef.current?.focus();
                  }}
                  aria-label="Clear search"
                  className="grid h-5 w-5 place-items-center rounded-full text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                >
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" aria-hidden>
                    <path
                      d="M6 6l12 12M18 6L6 18"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
              )}
              {!draft && (
                <kbd className="hidden rounded border border-zinc-200 px-1.5 py-0.5 text-[10px] text-zinc-400 sm:block dark:border-zinc-700">
                  /
                </kbd>
              )}
            </div>
          </div>
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="rounded-xl bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-opacity disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {busy ? "Searching…" : "Search"}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-4 text-xs text-zinc-500">
          <label className="flex items-center gap-2">
            Results
            <select
              value={limit}
              onChange={(e) => go({ limit: Number(e.target.value), replace: true })}
              className="rounded-md bg-white px-2 py-1 ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800"
            >
              {[3, 5, 10, 20].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-2">
            Scope
            <select
              value={documentId}
              onChange={(e) => go({ doc: e.target.value, replace: true })}
              className="max-w-64 rounded-md bg-white px-2 py-1 ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800"
            >
              <option value="">All documents</option>
              {documents.map((d) => (
                <option key={d.document_id} value={d.document_id}>
                  {d.original_filename} ({d.document_id.slice(0, 8)})
                </option>
              ))}
            </select>
          </label>

          <span className="ml-auto flex items-center gap-3">
            {entries.length > 0 && (
              <span className="hidden sm:inline">↑↓ recall</span>
            )}
            {response && (
              <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-medium dark:bg-zinc-800">
                {response.mode}
              </span>
            )}
            {elapsed !== null && <span>{elapsed.toFixed(0)} ms</span>}
            {indexed !== null && <span>{indexed} chunks indexed</span>}
          </span>
        </div>
      </form>

      <HistoryPanel
        entries={entries}
        activeQuery={query}
        onPick={(q) => go({ q })}
        onRemove={remove}
        onClear={clear}
        label="Recent searches"
      />

      {!query && !error && (
        <Suggestions
          asked={entries.map((e) => e.query)}
          onPick={(q) => go({ q })}
          hint="Generated from the documents you've indexed."
        />
      )}

      {error && (
        <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-red-200 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/30">
          {error}
        </p>
      )}

      {response && response.results.length === 0 && (
        <p className="rounded-xl border border-dashed border-zinc-300 px-4 py-10 text-center text-sm text-zinc-500 dark:border-zinc-700">
          Nothing matched. Upload a document, or try different wording.
        </p>
      )}

      {response && response.results.length > 0 && (
        <ol className="space-y-3">
          {response.results.map((hit, rank) => (
            <li
              key={`${hit.document_id}-${hit.chunk_index}`}
              className="rise rounded-xl bg-white p-4 shadow-sm ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800"
            >
              <div className="mb-2.5">
                <HitMeta hit={hit} rank={rank + 1} />
              </div>
              <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
                {hit.text}
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
