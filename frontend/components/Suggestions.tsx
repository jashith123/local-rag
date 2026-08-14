"use client";

import { useEffect, useState } from "react";
import { suggestions as fetchSuggestions } from "@/lib/api";

/**
 * Example questions generated from the indexed documents, minus anything the
 * user has already asked — a suggestion you've used is just clutter.
 *
 * Two presentations, because the same content plays two different roles:
 *
 *   "empty"  the page has no content yet, so this *is* the content. A framed,
 *            centered block is right here.
 *   "inline" a conversation is already on screen. The dashed frame would read
 *            as "nothing here yet" directly beneath a real answer, so this is
 *            a quiet row instead, sitting next to the input it fills.
 */
export function Suggestions({
  asked,
  onPick,
  variant = "empty",
  heading = "Try one of these",
  hint,
  max = 3,
}: {
  asked: string[];
  onPick: (question: string) => void;
  variant?: "empty" | "inline";
  heading?: string;
  hint?: string;
  max?: number;
}) {
  const [items, setItems] = useState<string[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    // Deferred so the setState never lands synchronously inside the effect.
    const handle = setTimeout(async () => {
      try {
        const data = await fetchSuggestions();
        if (!cancelled) setItems(data.suggestions);
      } catch {
        if (!cancelled) setFailed(true);
      }
    }, 0);

    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, []);

  const askedSet = new Set(asked.map((q) => q.trim().toLowerCase()));
  const remaining = (items ?? [])
    .filter((q) => !askedSet.has(q.trim().toLowerCase()))
    .slice(0, max);

  if (failed) return null;
  if (items !== null && remaining.length === 0) return null;

  const chip =
    "rounded-full bg-white px-3 py-1.5 text-xs ring-1 ring-zinc-200 transition-colors hover:bg-zinc-100 dark:bg-zinc-900 dark:ring-zinc-800 dark:hover:bg-zinc-800";

  if (variant === "inline") {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-zinc-400">Next</span>
        {items === null
          ? [40, 52].map((w) => (
              <span
                key={w}
                className="skeleton h-7 rounded-full bg-zinc-200 dark:bg-zinc-800"
                style={{ width: `${w * 3}px` }}
              />
            ))
          : remaining.map((question) => (
              <button
                key={question}
                type="button"
                onClick={() => onPick(question)}
                className={chip}
              >
                {question}
              </button>
            ))}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-dashed border-zinc-300 px-6 py-8 text-center dark:border-zinc-700">
      <p className="text-sm font-medium">{heading}</p>
      {hint && (
        <p className="mx-auto mt-1 max-w-md text-xs text-zinc-500">{hint}</p>
      )}

      <div className="mt-3 flex flex-wrap justify-center gap-2">
        {items === null
          ? // First load generates one question per document with the local
            // model, which takes a few seconds — show its shape meanwhile.
            [56, 44, 64].map((w) => (
              <span
                key={w}
                className="skeleton h-7 rounded-full bg-zinc-200 dark:bg-zinc-800"
                style={{ width: `${w * 4}px` }}
              />
            ))
          : remaining.map((question) => (
              <button
                key={question}
                type="button"
                onClick={() => onPick(question)}
                className={chip}
              >
                {question}
              </button>
            ))}
      </div>
    </div>
  );
}
