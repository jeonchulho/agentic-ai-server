"""Factory for creating LangChain chat model instances.

Supported providers (set via the ``LLM_PROVIDER`` environment variable):
- ``openai``  (default) — OpenAI ChatGPT via ``langchain_openai.ChatOpenAI``
- ``ollama``            — Local Ollama server via OpenAI-compatible endpoint
- ``claude``            — Anthropic Claude via ``langchain_anthropic.ChatAnthropic``
- ``gemini``            — Google Gemini via ``langchain_google_genai.ChatGoogleGenerativeAI``
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.config import settings


def get_chat_model() -> BaseChatModel:
    """Return a LangChain ``BaseChatModel`` for the configured provider.

    Raises:
        ValueError: If ``LLM_PROVIDER`` is set to an unrecognised value.
        ImportError: If the required LangChain integration package is missing.
    """
    provider = settings.llm_provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    if provider == "ollama":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        # Ollama exposes an OpenAI-compatible HTTP API; a real key is not required.
        return ChatOpenAI(
            api_key="ollama",
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )

    if provider in ("claude", "anthropic"):
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=settings.claude_model,
        )

    if provider in ("gemini", "google"):
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415

        return ChatGoogleGenerativeAI(
            google_api_key=settings.google_api_key,
            model=settings.gemini_model,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        "Valid options: openai, ollama, claude, gemini"
    )
