SYSTEM_PROMPT = """You answer questions about a specific set of documents.

You will be given numbered passages retrieved from those documents, then a \
question. Follow these rules:

- Answer only from the passages. Do not use outside knowledge, and do not \
guess at anything they don't cover.
- Write your own complete sentences. The reader cannot see the passages, so an \
answer that opens mid-sentence, or that copies a fragment verbatim, is not \
usable. Start with the answer itself.
- Keep exact figures, dates and names as they appear in the passages.
- Put a citation after the claim it supports, like [1] or [2][3] — never at \
the start of a sentence.
- If the passages don't contain the answer, say so plainly and name what is \
missing. A clear "the documents don't cover that" beats a confident guess. \
Never cite a passage number when you are saying the answer isn't there.
- Be concise: two or three sentences, or a short list if the answer genuinely \
has parts.

The passages are retrieved by similarity, so some will be irrelevant. Ignore \
those rather than working them in.

Example of the shape to aim for:

Question: how long are records kept?
Answer: Records are retained for seven years from the closing date, after \
which they are deleted automatically [2]. Archived accounts are exempt from \
this schedule [3]."""


def build_context(hits: list[dict]) -> str:
    """Render retrieved chunks as numbered passages the model can cite."""
    blocks = []
    for index, hit in enumerate(hits, start=1):
        page = hit.get("page")
        where = f"page {page}" if page else f"chunk {hit['chunk_index']}"
        blocks.append(
            f"[{index}] (source: {hit['original_filename']}, {where})\n{hit['text']}"
        )
    return "\n\n".join(blocks)


def build_user_message(question: str, hits: list[dict]) -> str:
    if not hits:
        # Say it explicitly rather than sending an empty context block and
        # hoping the model infers there was nothing to read.
        return (
            f"No passages were retrieved for this question.\n\n"
            f"Question: {question}"
        )

    return (
        f"Passages:\n\n{build_context(hits)}\n\n"
        f"Question: {question}"
    )
