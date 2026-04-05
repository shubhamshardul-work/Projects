"""
LLM Factory — multi-provider LLM instantiation.

Supports: groq, gemini, openai
Controlled via LLM_PROVIDER env var in .env
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from src.config import (
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    GROQ_API_KEY,
    GROQ_MODEL,
    GOOGLE_API_KEY,
    GEMINI_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from src.utils.logger import log


def _build_groq(
    model: str | None = None,
    temperature: float | None = None,
    **kwargs,
) -> BaseChatModel:
    """Instantiate a Groq-backed chat model."""
    from langchain_groq import ChatGroq

    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in .env")

    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=model or GROQ_MODEL,
        temperature=temperature if temperature is not None else LLM_TEMPERATURE,
        **kwargs,
    )


def _build_gemini(
    model: str | None = None,
    temperature: float | None = None,
    **kwargs,
) -> BaseChatModel:
    """Instantiate a Google Gemini-backed chat model."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not set in .env")

    return ChatGoogleGenerativeAI(
        google_api_key=GOOGLE_API_KEY,
        model=model or GEMINI_MODEL,
        temperature=temperature if temperature is not None else LLM_TEMPERATURE,
        **kwargs,
    )


def _build_openai(
    model: str | None = None,
    temperature: float | None = None,
    **kwargs,
) -> BaseChatModel:
    """Instantiate an OpenAI-backed chat model."""
    from langchain_openai import ChatOpenAI

    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set in .env")

    return ChatOpenAI(
        api_key=OPENAI_API_KEY,
        model=model or OPENAI_MODEL,
        temperature=temperature if temperature is not None else LLM_TEMPERATURE,
        **kwargs,
    )


_FACTORIES = {
    "groq": _build_groq,
    "gemini": _build_gemini,
    "openai": _build_openai,
}


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    **kwargs,
) -> BaseChatModel:
    """
    Return a LangChain ChatModel based on the chosen provider.

    Args:
        provider:    Override LLM_PROVIDER from .env (groq | gemini | openai).
        model:       Override the default model for the provider.
        temperature: Override the default temperature.
        **kwargs:    Extra kwargs forwarded to the underlying ChatModel.

    Returns:
        A LangChain ChatModel instance.
    """
    provider = (provider or LLM_PROVIDER).lower().strip()

    if provider not in _FACTORIES:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Choose from: {list(_FACTORIES.keys())}"
        )

    log.info(f"[bold cyan]LLM Factory[/] → provider=[bold]{provider}[/]")
    llm = _FACTORIES[provider](model=model, temperature=temperature, **kwargs)
    log.info(f"[bold cyan]LLM Factory[/] → model=[bold]{llm.model_name if hasattr(llm, 'model_name') else model or 'default'}[/]")
    return llm
