"use client";

import { useCallback, useSyncExternalStore } from "react";
import type { ChatDone, SearchHit } from "./api";

export interface ChatTurn {
  id: string;
  question: string;
  /** Set when a follow-up was rewritten into a standalone question before
   *  retrieval — shown so the resolution is visible, not magic. */
  searchQuery?: string;
  answer: string;
  sources: SearchHit[];
  done: ChatDone | null;
  error: string | null;
}

export interface Conversation {
  id: string;
  title: string;
  /** Epoch ms of the last message. */
  at: number;
  turns: ChatTurn[];
}

interface State {
  conversations: Conversation[];
  activeId: string | null;
}

const KEY = "eaip:conversations";
const LIMIT = 20;

// Snapshots are compared by reference, so the parsed value is cached and only
// replaced on an actual write — re-parsing per call would loop forever.
let cache: State | null = null;
const listeners = new Set<() => void>();

const EMPTY: State = { conversations: [], activeId: null };

function read(): State {
  if (cache) return cache;

  let state = EMPTY;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as State;
      if (Array.isArray(parsed?.conversations)) state = parsed;
    }
  } catch {
    // Corrupt storage shouldn't take the page down.
  }
  cache = state;
  return state;
}

function write(state: State) {
  cache = state;
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // Over quota or private mode — keep it for this session at least.
  }
  listeners.forEach((notify) => notify());
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  const onStorage = (event: StorageEvent) => {
    if (event.key === KEY) {
      cache = null;
      onChange();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onStorage);
  };
}

function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function titleFrom(turns: ChatTurn[]) {
  const first = turns[0]?.question ?? "New chat";
  return first.length > 60 ? `${first.slice(0, 57)}…` : first;
}

/**
 * Conversations, persisted to localStorage.
 *
 * Chat state used to live only in component state, so navigating to Documents
 * and back — or reloading — silently destroyed the conversation.
 */
export function useConversations() {
  const state = useSyncExternalStore(subscribe, read, () => EMPTY);

  const active =
    state.conversations.find((c) => c.id === state.activeId) ?? null;

  /** Replace the active conversation's turns, creating it on first use. */
  const saveTurns = useCallback((turns: ChatTurn[]) => {
    const current = read();
    const id = current.activeId ?? newId();
    const existing = current.conversations.find((c) => c.id === id);

    const conversation: Conversation = {
      id,
      title: titleFrom(turns),
      at: Date.now(),
      turns,
    };

    const others = current.conversations.filter((c) => c.id !== id);
    write({
      // Most recently used first, so the switcher reads chronologically.
      conversations: [conversation, ...others].slice(0, LIMIT),
      activeId: id,
    });

    return existing;
  }, []);

  /** Start a fresh conversation. The current one stays in the list. */
  const startNew = useCallback(() => {
    const current = read();
    // Drop an untouched empty conversation rather than accumulating blanks.
    const conversations = current.conversations.filter(
      (c) => c.turns.length > 0,
    );
    write({ conversations, activeId: null });
  }, []);

  const open = useCallback((id: string) => {
    write({ ...read(), activeId: id });
  }, []);

  const remove = useCallback((id: string) => {
    const current = read();
    write({
      conversations: current.conversations.filter((c) => c.id !== id),
      activeId: current.activeId === id ? null : current.activeId,
    });
  }, []);

  const clearAll = useCallback(() => write(EMPTY), []);

  return {
    conversations: state.conversations,
    activeId: state.activeId,
    active,
    saveTurns,
    startNew,
    open,
    remove,
    clearAll,
  };
}
