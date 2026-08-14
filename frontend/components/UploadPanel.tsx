"use client";

import { useRef, useState } from "react";
import { ApiError, formatBytes, uploadDocument } from "@/lib/api";

// Mirrors MAX_UPLOAD_SIZE in backend/app/core/config.py. Checking here saves a
// pointless 25 MB upload, but the backend still enforces it — this is a
// convenience, not the security boundary.
const MAX_BYTES = 25 * 1024 * 1024;

const STAGES = ["extract", "chunk", "embed", "index"];

export function UploadPanel({ onUploaded }: { onUploaded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function send(file: File) {
    setError(null);
    setSuccess(null);

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError(`Only PDF files are allowed — "${file.name}" is not a PDF.`);
      return;
    }
    if (file.size > MAX_BYTES) {
      setError(
        `${file.name} is ${formatBytes(file.size)}, over the 25 MB limit.`,
      );
      return;
    }

    setBusy(true);
    try {
      const result = await uploadDocument(file);
      setSuccess(result.document.original_filename);
      onUploaded();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Upload failed unexpectedly.",
      );
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <section>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files?.[0];
          if (file) void send(file);
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        className={`group cursor-pointer rounded-xl border-2 border-dashed px-6 py-10 text-center transition-all ${
          dragging
            ? "scale-[1.01] border-zinc-900 bg-zinc-100 dark:border-zinc-100 dark:bg-zinc-800"
            : "border-zinc-300 hover:border-zinc-400 hover:bg-white dark:border-zinc-700 dark:hover:border-zinc-600 dark:hover:bg-zinc-900"
        } ${busy ? "pointer-events-none opacity-60" : ""}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void send(file);
          }}
        />

        <svg
          viewBox="0 0 24 24"
          className="mx-auto h-7 w-7 text-zinc-400 transition-transform group-hover:-translate-y-0.5"
          aria-hidden
        >
          <path
            d="M12 16V4m0 0L8 8m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>

        <p className="mt-3 text-sm font-medium">
          {busy ? "Uploading…" : "Drop a PDF here, or click to choose one"}
        </p>
        <p className="mt-1 text-xs text-zinc-500">PDF only · up to 25 MB</p>

        {/* Naming the stages makes the wait legible: the row below stays on
            "processing" for a while, and this says what is happening in it. */}
        <div className="mt-4 flex items-center justify-center gap-1.5 text-[11px] text-zinc-400">
          {STAGES.map((stage, i) => (
            <span key={stage} className="flex items-center gap-1.5">
              {i > 0 && <span aria-hidden>→</span>}
              <span className="rounded bg-zinc-100 px-1.5 py-0.5 dark:bg-zinc-800">
                {stage}
              </span>
            </span>
          ))}
        </div>
      </div>

      {error && (
        <p className="rise mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-red-200 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/30">
          {error}
        </p>
      )}
      {success && !error && (
        <p className="rise mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30">
          <span className="font-medium">{success}</span> uploaded — extracting
          and embedding in the background.
        </p>
      )}
    </section>
  );
}
