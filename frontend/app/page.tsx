"use client";

import { useState } from "react";
import { DocumentList } from "@/components/DocumentList";
import { StatTiles } from "@/components/StatTiles";
import { UploadPanel } from "@/components/UploadPanel";
import { useDocuments } from "@/lib/useDocuments";

export default function DocumentsPage() {
  // Bumping this restarts the poller. Simplest possible invalidation:
  // upload finishes -> token changes -> the hook refetches.
  const [refreshToken, setRefreshToken] = useState(0);
  const { documents, indexedChunks, loading, error } =
    useDocuments(refreshToken);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Each PDF is extracted, split into overlapping chunks, embedded locally
          and indexed into Qdrant — searchable by meaning, not keywords.
        </p>
      </div>

      <StatTiles
        documents={documents}
        indexedChunks={indexedChunks}
        loading={loading}
      />

      <UploadPanel onUploaded={() => setRefreshToken((n) => n + 1)} />

      <DocumentList documents={documents} loading={loading} error={error} />
    </div>
  );
}
