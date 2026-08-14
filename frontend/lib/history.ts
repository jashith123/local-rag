"use client";

import { useCallback, useSyncExternalStore } from "react";

export interface HistoryEntry {
  id: string;
  query: string;
  /** Epoch ms. */
  at: number;
  /** Short result summary, e.g. "5 hits · 0.579" or "3 sources". */
  meta?: string;
}

export type HistoryScope = "search" | "chat";

const LIMIT = 25;

const storageKey = (scope: HistoryScope) => `eaip:history:${scope}`;

// useSyncExternalStore compares snapshots by reference and re-renders on any
// change. Parsing localStorage on every call would return a fresh array each
// time and loop forever, so the parsed value is cached and only replaced when
// the data actually changes.
const cache = new Map<HistoryScope, HistoryEntry[]>();
const listeners = new Map<HistoryScope, Set<() => void>>();

// A single frozen reference for "nothing", shared by the server snapshot and
// every empty read — same reasoning as above.
const EMPTY: HistoryEntry[] = [];

function read(scope: HistoryScope): HistoryEntry[] {
  const cached = cache.get(scope);
  if (cached) return cached;

  let entries: HistoryEntry[] = EMPTY;
  try {
    const raw = localStorage.getItem(storageKey(scope));
    if (raw) {
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed)) entries = parsed as HistoryEntry[];
    }
  } catch {
    // Corrupt or unavailable storage shouldn't break the page.
  }

  cache.set(scope, entries);
  return entries;
}

function emit(scope: HistoryScope) {
  listeners.get(scope)?.forEach((notify) => notify());
}

function write(scope: HistoryScope, entries: HistoryEntry[]) {
  cache.set(scope, entries);
  try {
    localStorage.setItem(storageKey(scope), JSON.stringify(entries));
  } catch {
    // Over quota or private mode — keep it in memory for this session.
  }
  emit(scope);
}

function subscribe(scope: HistoryScope, onChange: () => void) {
  let set = listeners.get(scope);
  if (!set) {
    set = new Set();
    listeners.set(scope, set);
  }
  set.add(onChange);

  // Another tab writing the same key should update this one too.
  const onStorage = (event: StorageEvent) => {
    if (event.key === storageKey(scope)) {
      cache.delete(scope);
      onChange();
    }
  };
  window.addEventListener("storage", onStorage);

  return () => {
    set?.delete(onChange);
    window.removeEventListener("storage", onStorage);
  };
}

export function useHistory(scope: HistoryScope) {
  const entries = useSyncExternalStore(
    useCallback((onChange: () => void) => subscribe(scope, onChange), [scope]),
    useCallback(() => read(scope), [scope]),
    () => EMPTY,
  );

  const add = useCallback(
    (query: string, meta?: string) => {
      const trimmed = query.trim();
      if (!trimmed) return;

      const current = read(scope);
      // Re-running an old query should move it to the top, not add a duplicate.
      const withoutDuplicate = current.filter(
        (e) => e.query.toLowerCase() !== trimmed.toLowerCase(),
      );
      const entry: HistoryEntry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        query: trimmed,
        at: Date.now(),
        meta,
      };
      write(scope, [entry, ...withoutDuplicate].slice(0, LIMIT));
    },
    [scope],
  );

  const remove = useCallback(
    (id: string) => write(scope, read(scope).filter((e) => e.id !== id)),
    [scope],
  );

  const clear = useCallback(() => write(scope, []), [scope]);

  return { entries, add, remove, clear };
}

export function relativeTime(at: number): string {
  const seconds = Math.round((Date.now() - at) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}
