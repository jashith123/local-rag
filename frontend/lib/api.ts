// Typed client for the FastAPI backend. Shapes mirror backend/app/schemas/.
// Every path goes through /api/*, which next.config.ts rewrites to the backend.

export type DocumentStatus = "uploaded" | "processing" | "processed" | "failed";

export interface DocumentMetadata {
  document_id: string;
  original_filename: string;
  stored_filename: string;
  content_type: string;
  size: number;
  uploaded_at: string;
  status: DocumentStatus;
  page_count: number | null;
  character_count: number | null;
  chunk_count: number | null;
  vector_count: number | null;
  error: string | null;
}

export interface UploadResponse {
  message: string;
  document: DocumentMetadata;
}

export interface DocumentListResponse {
  count: number;
  documents: DocumentMetadata[];
}

export interface SearchHit {
  score: number;
  document_id: string;
  original_filename: string;
  chunk_index: number;
  text: string;
}

export interface SearchResponse {
  query: string;
  count: number;
  results: SearchHit[];
}

/** Thrown for any non-2xx response, carrying the backend's own message. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * FastAPI reports errors as {detail: ...}, where detail is a plain string for
 * HTTPException (our 400s, 404s, 413s) but an array of objects for Pydantic
 * validation failures (422). Flatten both into one readable line.
 */
async function readError(response: Response): Promise<string> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return `${response.status} ${response.statusText}`;
  }

  const detail = (body as { detail?: unknown })?.detail;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const entry = item as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(entry.loc) ? entry.loc.at(-1) : undefined;
        return field ? `${field}: ${entry.msg}` : entry.msg;
      })
      .filter(Boolean)
      .join("; ");
  }

  return `${response.status} ${response.statusText}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch {
    // fetch only rejects on a transport failure, which here almost always
    // means the backend isn't running.
    throw new ApiError(
      "Cannot reach the backend. Is uvicorn running on port 8000?",
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  return (await response.json()) as T;
}

export function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  // Deliberately no Content-Type header — the browser must set it itself so it
  // can append the multipart boundary.
  return request<UploadResponse>("/documents/upload", {
    method: "POST",
    body: form,
  });
}

export function listDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>("/documents", { cache: "no-store" });
}

export function getDocument(id: string): Promise<DocumentMetadata> {
  return request<DocumentMetadata>(`/documents/${id}`, { cache: "no-store" });
}

export function search(
  query: string,
  limit = 5,
  documentId?: string,
): Promise<SearchResponse> {
  return request<SearchResponse>("/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      limit,
      document_id: documentId || null,
    }),
  });
}

export interface ChatUsage {
  input_tokens: number;
  output_tokens: number;
}

export interface ChatDone {
  provider: string;
  model: string;
  billed: boolean;
  usage: ChatUsage;
}

export interface ChatConfig {
  provider: string;
  model: string;
  billed: boolean;
}

export interface ChatHandlers {
  onSources: (sources: SearchHit[]) => void;
  onDelta: (text: string) => void;
  onDone: (info: ChatDone) => void;
  onError: (message: string) => void;
}

export function chatConfig(): Promise<ChatConfig> {
  return request<ChatConfig>("/chat/config", { cache: "no-store" });
}

/**
 * Stream an answer over Server-Sent Events.
 *
 * EventSource can't POST, so this reads the body by hand. Once the response
 * has started the status is fixed at 200, which is why failures arrive as an
 * `error` event rather than an HTTP code.
 */
export async function streamChat(
  body: { question: string; top_k?: number; document_id?: string | null },
  handlers: ChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if ((err as Error)?.name === "AbortError") return;
    handlers.onError(
      "Cannot reach the backend. Is uvicorn running on port 8000?",
    );
    return;
  }

  if (!response.ok || !response.body) {
    handlers.onError(await readError(response));
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    let chunk;
    try {
      chunk = await reader.read();
    } catch {
      return; // aborted mid-stream
    }
    if (chunk.done) break;

    buffer += decoder.decode(chunk.value, { stream: true });

    // SSE frames are separated by a blank line. Keep the trailing partial
    // frame in the buffer until the rest of it arrives.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;

      let payload: Record<string, unknown>;
      try {
        payload = JSON.parse(data);
      } catch {
        continue;
      }

      if (event === "sources") {
        handlers.onSources((payload.sources ?? []) as SearchHit[]);
      } else if (event === "delta") {
        handlers.onDelta(payload.text as string);
      } else if (event === "done") {
        handlers.onDone(payload as unknown as ChatDone);
      } else if (event === "error") {
        handlers.onError(payload.message as string);
      }
    }
  }
}

/** Example questions generated from the documents that are actually indexed. */
export function suggestions(): Promise<{
  suggestions: string[];
  generated: boolean;
}> {
  return request<{ suggestions: string[]; generated: boolean }>(
    "/suggestions",
    { cache: "no-store" },
  );
}

export function searchStats(): Promise<{ indexed_chunks: number }> {
  return request<{ indexed_chunks: number }>("/search/stats", {
    cache: "no-store",
  });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
