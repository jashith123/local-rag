from app.llm.base import LLMError, Message
from app.llm.provider import get_provider

SYSTEM = (
    "You rewrite a follow-up question so it can be understood on its own.\n\n"
    "Replace pronouns and references like 'it', 'that', 'this one', 'the same' "
    "with what they actually refer to in the conversation. Keep the user's own "
    "words wherever you can, and keep it short.\n\n"
    "Reply with the rewritten question only - no preamble, no quotes, no "
    "explanation. If the question already stands on its own, reply with it "
    "unchanged."
)

# A rewrite that comes back longer than this is the model explaining itself
# rather than rewriting, so the original is safer.
_MAX_LENGTH = 300


def _looks_standalone(question: str) -> bool:
    """Cheap check for whether a rewrite is even needed.

    Rewriting costs a model call, so skip it for questions that clearly carry
    their own subject. Only obvious back-references are worth the round trip.
    """
    lowered = f" {question.lower().strip()} "
    referring = (
        " it ", " it?", " its ", " that ", " this ", " they ", " them ",
        " those ", " these ", " he ", " she ", " same ", " one ", " there ",
    )
    if any(word in lowered for word in referring):
        return False
    # A very short question is usually elliptical: "how fast?", "why?"
    return len(question.split()) > 4


def rewrite(question: str, history: list[Message]) -> tuple[str, bool]:
    """Turn a follow-up into a standalone question for retrieval.

    Returns (query_to_search_with, was_rewritten).

    This matters more than it looks. Feeding "how fast is it" to the embedder
    retrieves passages about speed in general, so the model gets the wrong
    context and correctly reports it cannot answer. The generation step sees
    the conversation and could resolve "it" itself - retrieval cannot, because
    it only ever sees the query string.
    """
    if not history or _looks_standalone(question):
        return question, False

    # Only the last few turns matter for resolving a pronoun, and a short
    # prompt keeps this fast enough to sit in front of every follow-up.
    recent = history[-4:]
    transcript = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in recent
    )

    try:
        rewritten, _ = get_provider().complete(
            SYSTEM,
            [
                {
                    "role": "user",
                    "content": (
                        f"Conversation so far:\n{transcript}\n\n"
                        f"Follow-up question: {question}\n\n"
                        f"Rewritten standalone question:"
                    ),
                }
            ],
        )
    except (LLMError, Exception):
        # A failed rewrite must not take the question down with it.
        return question, False

    cleaned = rewritten.strip().strip('"').splitlines()[0].strip() if rewritten else ""
    if not cleaned or len(cleaned) > _MAX_LENGTH:
        return question, False

    return cleaned, cleaned.lower() != question.strip().lower()
