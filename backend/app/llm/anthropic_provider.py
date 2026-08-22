import threading
from typing import Iterator

import anthropic

from app.core.config import ANTHROPIC_API_KEY, CHAT_MAX_TOKENS, CHAT_MODEL
from app.llm.base import DoneInfo, LLMError, Message

_client: anthropic.Anthropic | None = None
_lock = threading.Lock()


def _get_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise LLMError(
            "No ANTHROPIC_API_KEY configured. Add it to backend/.env as "
            "ANTHROPIC_API_KEY=sk-ant-..., or set CHAT_PROVIDER=ollama to use "
            "a local model instead. Keys: https://console.anthropic.com/settings/keys"
        )

    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _wrap(exc: Exception) -> LLMError:
    if isinstance(exc, LLMError):
        return exc
    if isinstance(exc, anthropic.AuthenticationError):
        return LLMError(
            "Anthropic rejected the API key. Check ANTHROPIC_API_KEY in backend/.env"
        )
    if isinstance(exc, anthropic.RateLimitError):
        return LLMError("Rate limited by the Anthropic API. Wait a moment and retry.")
    if isinstance(exc, anthropic.APIConnectionError):
        return LLMError("Could not reach the Anthropic API. Check your connection.")
    return LLMError(f"Answer generation failed: {exc}")


class AnthropicProvider:
    name = "anthropic"
    billed = True

    def __init__(self) -> None:
        self.model = CHAT_MODEL

    def complete(self, system: str, messages: list[Message]) -> tuple[str, DoneInfo]:
        try:
            message = _get_client().messages.create(
                model=CHAT_MODEL,
                max_tokens=CHAT_MAX_TOKENS,
                system=system,
                messages=list(messages),
            )
        except Exception as exc:
            raise _wrap(exc) from exc

        text = "".join(
            block.text for block in message.content if block.type == "text"
        )
        return (
            text,
            {
                "model": message.model,
                "usage": {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                },
            },
        )

    def stream(self, system: str, messages: list[Message]) -> Iterator[tuple[str, dict]]:
        try:
            with _get_client().messages.stream(
                model=CHAT_MODEL,
                max_tokens=CHAT_MAX_TOKENS,
                system=system,
                messages=list(messages),
            ) as stream:
                for text in stream.text_stream:
                    yield ("delta", {"text": text})
                final = stream.get_final_message()

            yield (
                "done",
                {
                    "model": final.model,
                    "usage": {
                        "input_tokens": final.usage.input_tokens,
                        "output_tokens": final.usage.output_tokens,
                    },
                },
            )
        except Exception as exc:
            raise _wrap(exc) from exc
