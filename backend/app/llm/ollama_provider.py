import json
from typing import Iterator

import httpx

from app.core.config import (
    CHAT_MAX_TOKENS,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_URL
)
from app.llm.base import DoneInfo, LLMError

# A 3B model on CPU is not fast; the whole answer can take half a minute.
# Streaming hides most of that, but the client still needs a generous ceiling.
_TIMEOUT = httpx.Timeout(300.0, connect=5.0)


def _options() -> dict:
    return {
        # Low but not zero: grounded answers should stick to the passages,
        # while a flat 0 makes small models loop on repeated phrases.
        "temperature": 0.2,
        "num_predict": CHAT_MAX_TOKENS,
        # Ollama's default context is small enough to silently truncate five
        # retrieved passages, which looks like the model ignoring them.
        "num_ctx": OLLAMA_NUM_CTX,
    }


def _payload(system: str, user: str, stream: bool) -> dict:
    return {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": stream,
        "options": _options(),
    }


def _usage(data: dict) -> dict:
    return {
        "input_tokens": data.get("prompt_eval_count", 0),
        "output_tokens": data.get("eval_count", 0),
    }


def _wrap(exc: Exception) -> LLMError:
    if isinstance(exc, httpx.ConnectError):
        return LLMError(
            f"Cannot reach Ollama at {OLLAMA_URL}. Start it with `ollama serve`."
        )
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return LLMError(
            f"Ollama has no model named '{OLLAMA_MODEL}'. "
            f"Pull it with `ollama pull {OLLAMA_MODEL}`, or set OLLAMA_MODEL "
            f"in backend/.env to one you have."
        )
    if isinstance(exc, httpx.ReadTimeout):
        return LLMError(
            "Ollama took too long to respond. Try a smaller model, "
            "e.g. OLLAMA_MODEL=llama3.2:3b in backend/.env"
        )
    return LLMError(f"Ollama request failed: {exc}")


class OllamaProvider:
    name = "ollama"
    billed = False

    def __init__(self) -> None:
        self.model = OLLAMA_MODEL

    def complete(self, system: str, user: str) -> tuple[str, DoneInfo]:
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.post(
                    f"{OLLAMA_URL}/api/chat",
                    json=_payload(system, user, stream=False),
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            raise _wrap(exc) from exc

        return (
            data["message"]["content"].strip(),
            {"model": data.get("model", OLLAMA_MODEL), "usage": _usage(data)},
        )

    def stream(self, system: str, user: str) -> Iterator[tuple[str, dict]]:
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                with client.stream(
                    "POST",
                    f"{OLLAMA_URL}/api/chat",
                    json=_payload(system, user, stream=True),
                ) as response:
                    response.raise_for_status()

                    # Ollama streams newline-delimited JSON, one object per token
                    # batch, with the final object carrying the token counts.
                    for line in response.iter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)

                        if data.get("done"):
                            yield (
                                "done",
                                {
                                    "model": data.get("model", OLLAMA_MODEL),
                                    "usage": _usage(data),
                                },
                            )
                            return

                        text = (data.get("message") or {}).get("content", "")
                        if text:
                            yield ("delta", {"text": text})
        except Exception as exc:
            raise _wrap(exc) from exc
