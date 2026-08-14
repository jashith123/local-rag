from app.core.config import CHAT_PROVIDER
from app.llm.base import LLMError, LLMProvider

_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Return the configured backend.

    Set CHAT_PROVIDER in backend/.env:
      ollama    - a local model, free and offline (default)
      anthropic - the Claude API, needs ANTHROPIC_API_KEY
    """
    global _provider
    if _provider is not None:
        return _provider

    if CHAT_PROVIDER == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        _provider = OllamaProvider()
    elif CHAT_PROVIDER == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        _provider = AnthropicProvider()
    else:
        raise LLMError(
            f"Unknown CHAT_PROVIDER '{CHAT_PROVIDER}'. Use 'ollama' or 'anthropic'."
        )

    return _provider
