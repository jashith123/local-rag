"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  chatConfig,
  listDocuments,
  streamChat,
  type ChatConfig,
  type ChatUsage,
  type DocumentMetadata,
} from "@/lib/api";
import { useConversations, type ChatTurn } from "@/lib/conversations";
import { relativeTime } from "@/lib/history";
import { HitMeta } from "./HitMeta";
import { Suggestions } from "./Suggestions";

// Claude Haiku 4.5 list pricing, per million tokens. Only applied when the
// backend reports a billed provider — a local Ollama model costs nothing, and
// showing it "$0.00" would imply a meter that isn't running.
const IN_PER_MTOK = 1;
const OUT_PER_MTOK = 5;

function estimateCost(usage: ChatUsage) {
  return (
    (usage.input_tokens / 1_000_000) * IN_PER_MTOK +
    (usage.output_tokens / 1_000_000) * OUT_PER_MTOK
  );
}

/** Render [1] / [2][3] markers as chips tied to that turn's sources. */
function WithCitations({ text, turnId }: { text: string; turnId: string }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = /^\[(\d+)\]$/.exec(part);
        if (!match) return <span key={i}>{part}</span>;
        return (
          <a
            key={i}
            href={`#source-${turnId}-${match[1]}`}
            className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-zinc-900 px-1 align-super text-[10px] font-semibold text-white no-underline transition-opacity hover:opacity-80 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {match[1]}
          </a>
        );
      })}
    </>
  );
}

export function ChatPanel() {
  const [question, setQuestion] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [config, setConfig] = useState<ChatConfig | null>(null);
  const [busy, setBusy] = useState(false);

  // Which turn is mid-stream. Kept separate from the persisted turns so a
  // half-written answer is never saved as if it were finished.
  const [streamingId, setStreamingId] = useState<string | null>(null);

  const {
    conversations,
    activeId,
    saveTurns,
    startNew,
    open,
    remove,
    clearAll,
  } = useConversations();

  // The live view of the conversation, hydrated from storage on mount.
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listDocuments()
      .then((data) =>
        setDocuments(data.documents.filter((d) => d.status === "processed")),
      )
      .catch(() => undefined);
    chatConfig()
      .then(setConfig)
      .catch(() => undefined);
  }, []);

  // Load whichever conversation is active — on first mount, and whenever the
  // user switches or starts a new one.
  useEffect(() => {
    const handle = setTimeout(() => {
      const stored = activeId
        ? (conversations.find((c) => c.id === activeId)?.turns ?? [])
        : [];
      setTurns(stored);
    }, 0);
    return () => clearTimeout(handle);
    // Deliberately keyed on the id only: re-running on every `conversations`
    // change would clobber the live turns mid-stream.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  useEffect(() => () => abortRef.current?.abort(), []);

  // Persist once a turn settles. Writing on every token would hit localStorage
  // hundreds of times per answer, and a half-streamed answer shouldn't be
  // saved as though it were finished.
  useEffect(() => {
    if (streamingId || turns.length === 0) return;
    saveTurns(turns);
  }, [turns, streamingId, saveTurns]);

  const ask = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busy) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const pending: ChatTurn = {
        id,
        question: trimmed,
        answer: "",
        sources: [],
        done: null,
        error: null,
      };

      setTurns((prev) => [...prev, pending]);
      setStreamingId(id);
      setQuestion("");
      setBusy(true);

      requestAnimationFrame(() =>
        endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }),
      );

      const update = (change: Partial<ChatTurn>) =>
        setTurns((prev) =>
          prev.map((t) => (t.id === id ? { ...t, ...change } : t)),
        );

      await streamChat(
        { question: trimmed, top_k: 5, document_id: documentId || null },
        {
          onSources: (sources) => update({ sources }),
          onDelta: (delta) =>
            setTurns((prev) =>
              prev.map((t) =>
                t.id === id ? { ...t, answer: t.answer + delta } : t,
              ),
            ),
          onDone: (done) => update({ done }),
          onError: (error) => update({ error }),
        },
        controller.signal,
      );

      setStreamingId(null);
      setBusy(false);
    },
    [busy, documentId],
  );

  const meta = turns.at(-1)?.done ?? config;
  const askedInThisChat = turns.map((t) => t.question);

  return (
    <div className="space-y-6">
      {/* Conversation bar — always visible, so starting over is one click and
          the previous conversation is never lost by doing so. */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => {
            abortRef.current?.abort();
            startNew();
            setTurns([]);
            setQuestion("");
            setBusy(false);
            setStreamingId(null);
          }}
          className="flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 dark:bg-zinc-100 dark:text-zinc-900"
        >
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" aria-hidden>
            <path
              d="M12 5v14M5 12h14"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
          </svg>
          New chat
        </button>

        {conversations.length > 0 && (
          <>
            <span className="text-xs text-zinc-400">|</span>
            <div className="flex flex-wrap items-center gap-1.5">
              {conversations.map((conversation) => {
                const isActive = conversation.id === activeId;
                return (
                  <div
                    key={conversation.id}
                    className={`group flex items-center rounded-lg text-xs ring-1 transition-colors ${
                      isActive
                        ? "bg-zinc-100 ring-zinc-300 dark:bg-zinc-800 dark:ring-zinc-600"
                        : "ring-zinc-200 hover:bg-zinc-100 dark:ring-zinc-800 dark:hover:bg-zinc-800"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => open(conversation.id)}
                      title={`${conversation.title} · ${conversation.turns.length} question${
                        conversation.turns.length === 1 ? "" : "s"
                      } · ${relativeTime(conversation.at)}`}
                      className="max-w-48 truncate py-1.5 pl-2.5 pr-1"
                    >
                      {conversation.title}
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(conversation.id)}
                      aria-label={`Delete conversation "${conversation.title}"`}
                      className="mr-1 grid h-5 w-5 shrink-0 place-items-center rounded opacity-40 transition-opacity hover:opacity-100"
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
                );
              })}
              <button
                type="button"
                onClick={() => {
                  clearAll();
                  setTurns([]);
                }}
                className="ml-1 text-xs text-zinc-500 transition-colors hover:text-zinc-900 dark:hover:text-zinc-100"
              >
                Clear all
              </button>
            </div>
          </>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(question);
        }}
        className="space-y-3"
      >
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setQuestion("");
            }}
            placeholder="Ask a question about your documents…"
            aria-label="Question"
            className="flex-1 rounded-xl bg-white px-4 py-2.5 text-sm shadow-sm outline-none ring-1 ring-zinc-200 transition-shadow placeholder:text-zinc-400 focus:ring-2 focus:ring-zinc-900 dark:bg-zinc-900 dark:ring-zinc-800 dark:focus:ring-zinc-100"
          />
          <button
            type="submit"
            disabled={busy || !question.trim()}
            className="rounded-xl bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-opacity disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {busy ? "Thinking…" : "Ask"}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-4 text-xs text-zinc-500">
          <label className="flex items-center gap-2">
            Scope
            <select
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
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
            {meta && (
              <span className="flex items-center gap-1.5">
                <span
                  className={`rounded px-1.5 py-0.5 font-medium ${
                    meta.billed
                      ? "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
                      : "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300"
                  }`}
                >
                  {meta.billed ? "cloud" : "local · free"}
                </span>
                <span className="font-mono">{meta.model}</span>
              </span>
            )}
          </span>
        </div>
      </form>

      {/* Follow-ups belong beside the input they fill, not stranded at the
          bottom of the page a screen away from it. */}
      {turns.length > 0 && !busy && (
        <Suggestions
          variant="inline"
          asked={[
            ...askedInThisChat,
            ...conversations.flatMap((c) => c.turns.map((t) => t.question)),
          ]}
          onPick={(q) => void ask(q)}
          max={2}
        />
      )}

      {turns.length === 0 && (
        <Suggestions
          asked={conversations.flatMap((c) => c.turns.map((t) => t.question))}
          onPick={(q) => void ask(q)}
          heading="Ask something"
          hint="Questions drawn from the documents you've actually indexed. Answers cite the passages they came from."
        />
      )}

      <div className="space-y-6">
        {turns.map((turn) => (
          <article key={turn.id} className="rise space-y-3">
            <div className="flex items-start gap-2">
              <span className="mt-0.5 text-xs font-medium uppercase tracking-wide text-zinc-400">
                Q
              </span>
              <p className="text-sm font-medium">{turn.question}</p>
            </div>

            {turn.error ? (
              <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/30">
                {turn.error}
              </div>
            ) : (
              <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800">
                <p className="whitespace-pre-wrap text-sm leading-relaxed">
                  <WithCitations text={turn.answer} turnId={turn.id} />
                  {streamingId === turn.id && (
                    <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-zinc-900 align-text-bottom dark:bg-zinc-100" />
                  )}
                </p>

                {turn.done?.usage && turn.done.usage.output_tokens > 0 && (
                  <p className="mt-3 border-t border-zinc-100 pt-2 text-xs text-zinc-400 dark:border-zinc-800">
                    {turn.done.usage.input_tokens} in /{" "}
                    {turn.done.usage.output_tokens} out
                    {turn.done.billed &&
                      ` · ${
                        estimateCost(turn.done.usage) < 0.01
                          ? `${(estimateCost(turn.done.usage) * 100).toFixed(2)}¢`
                          : `$${estimateCost(turn.done.usage).toFixed(3)}`
                      }`}
                  </p>
                )}
              </div>
            )}

            {turn.sources.length > 0 && (
              <details>
                <summary className="cursor-pointer text-xs font-medium uppercase tracking-wide text-zinc-500 transition-colors hover:text-zinc-900 dark:hover:text-zinc-100">
                  {turn.sources.length} sources
                </summary>
                <ol className="mt-2 space-y-2">
                  {turn.sources.map((hit, i) => (
                    <li
                      key={`${hit.document_id}-${hit.chunk_index}`}
                      id={`source-${turn.id}-${i + 1}`}
                      className="scroll-mt-20 rounded-xl bg-white p-3 ring-1 ring-zinc-200 target:ring-2 target:ring-zinc-900 dark:bg-zinc-900 dark:ring-zinc-800 dark:target:ring-zinc-100"
                    >
                      <div className="mb-1.5 flex items-center gap-2 text-xs">
                        <span className="grid h-5 w-5 shrink-0 place-items-center rounded bg-zinc-900 text-[10px] font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
                          {i + 1}
                        </span>
                        <HitMeta hit={hit} />
                      </div>
                      <p className="line-clamp-3 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
                        {hit.text}
                      </p>
                    </li>
                  ))}
                </ol>
              </details>
            )}
          </article>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
