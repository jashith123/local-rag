from typing import Iterator, Protocol, TypedDict


class Usage(TypedDict):
    input_tokens: int
    output_tokens: int


class DoneInfo(TypedDict):
    model: str
    usage: Usage


class Message(TypedDict):
    #: "user" or "assistant"
    role: str
    content: str


class LLMError(Exception):
    """Any provider failure, already phrased for the user."""


class LLMProvider(Protocol):
    """What the chat endpoint needs from a model backend.

    Takes a message list rather than a single string so a conversation can be
    replayed: a follow-up like "how fast is it" only makes sense with the
    previous turns in front of the model.
    """

    name: str
    model: str
    #: Whether calls cost money — the UI hides cost for local models.
    billed: bool

    def complete(
        self, system: str, messages: list[Message]
    ) -> tuple[str, DoneInfo]:
        """Return the whole answer at once."""
        ...

    def stream(
        self, system: str, messages: list[Message]
    ) -> Iterator[tuple[str, dict]]:
        """Yield ("delta", {"text": ...}) repeatedly, then ("done", DoneInfo).

        The tuples map straight onto the SSE events the frontend consumes.
        """
        ...
