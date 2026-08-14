import { Suspense } from "react";
import { SearchPanel } from "@/components/SearchPanel";

export default function SearchPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Search</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Semantic, not keyword. Your question is embedded with the same model
          the documents were, so wording that never appears in the text can
          still match the right passage.
        </p>
      </div>

      {/* SearchPanel reads the query string, which opts it out of static
          prerendering — Next requires a Suspense boundary around that. */}
      <Suspense
        fallback={
          <div className="skeleton h-11 rounded-xl bg-zinc-200 dark:bg-zinc-800" />
        }
      >
        <SearchPanel />
      </Suspense>
    </div>
  );
}
