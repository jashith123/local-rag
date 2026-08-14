from typing import Iterator, Protocol, TypedDict


class Usage(TypedDict):
    input_tokens: int
    output_tokens: int


class DoneInfo(TypedDict):
    model: str
    usage: Usage


class LLMError(Exception):
    """Any provider failure, already phrased for the user."""


class LLMProvider(Protocol):
    """What the chat endpoint needs from a model backend.

    Deliberately small: two calls, no provider types leaking out. Adding a
    backend means implementing this, not touching the API layer.
    """

    name: str
    model: str
    #: Whether calls cost money — the UI hides cost for local models.
    billed: bool

    def complete(self, system: str, user: str) -> tuple[str, DoneInfo]:
        """Return the whole answer at once."""
        ...

    def stream(self, system: str, user: str) -> Iterator[tuple[str, dict]]:
        """Yield ("delta", {"text": ...}) repeatedly, then ("done", DoneInfo).

        The tuples map straight onto the SSE events the frontend consumes.
        """
        ...
