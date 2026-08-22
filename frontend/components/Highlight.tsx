const STOPWORDS = new Set([
  "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "is", "are",
  "was", "were", "be", "been", "it", "its", "this", "that", "these", "those",
  "as", "at", "by", "with", "from", "what", "which", "who", "how", "why",
  "do", "does", "did", "i", "you", "we", "they", "my", "me",
]);

/**
 * Bold the query's own words inside a retrieved passage.
 *
 * The passages are long and look alike; marking the terms turns a wall of text
 * into something scannable and shows at a glance *why* a result came back.
 * Stopwords are skipped - highlighting every "the" is noise, not signal.
 */
export function Highlight({ text, query }: { text: string; query: string }) {
  // Terms are extracted with [a-z0-9]+, so they cannot contain regex
  // metacharacters and need no escaping before going into the pattern below.
  const terms = Array.from(
    new Set(
      (query.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter(
        (word) => word.length > 2 && !STOPWORDS.has(word),
      ),
    ),
  );

  if (terms.length === 0) return <>{text}</>;

  // One pass over the text, splitting on any term. The word boundary keeps
  // "cycle" from matching inside "bicycle".
  const pattern = new RegExp("\\b(" + terms.join("|") + ")", "gi");
  const parts = text.split(pattern);

  return (
    <>
      {parts.map((part, i) =>
        terms.includes((part ?? "").toLowerCase()) ? (
          <mark
            key={i}
            className="rounded bg-amber-100 px-0.5 font-medium text-inherit dark:bg-amber-500/25"
          >
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}
