"""
LLM factory — returns the correct LangChain chat model based on LLM_PROVIDER.
Supports: openai, groq, gemini (switchable via .env).

For Gemini: implements round-robin key rotation across all GOOGLE_API_KEY*
and GEMINI_API_KEY* environment variables to distribute load across free-tier
quotas.
"""

from __future__ import annotations

import itertools
import logging
import os

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import (
    LLM_PROVIDER,
    LLM_MODEL,
    LLM_TEMPERATURE,
    DEFAULT_MODELS,
    OPENAI_API_KEY,
    GROQ_API_KEY,
    GEMINI_API_KEY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini API key pool — built once at import time
# ---------------------------------------------------------------------------

def _build_gemini_key_pool() -> list[str]:
    """
    Collect all GOOGLE_API_KEY* and GEMINI_API_KEY* values from the
    environment, filtering out placeholders and invalid entries.
    """
    keys: list[str] = []
    for env_name, env_val in sorted(os.environ.items()):
        if env_name.startswith(("GOOGLE_API_KEY", "GEMINI_API_KEY")) and env_val:
            # Skip obvious placeholders
            if "your_" in env_val.lower() or len(env_val) < 20:
                continue
            keys.append(env_val)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            unique.append(k)

    return unique


_GEMINI_KEY_POOL: list[str] = _build_gemini_key_pool()
_gemini_key_cycle = itertools.cycle(_GEMINI_KEY_POOL) if _GEMINI_KEY_POOL else None


def get_next_gemini_key() -> str:
    """Return the next Gemini API key from the round-robin pool."""
    if _gemini_key_cycle is None:
        logger.warning("No valid Gemini API keys found in environment, falling back to GEMINI_API_KEY")
        return GEMINI_API_KEY
    key = next(_gemini_key_cycle)
    # Log last 4 chars for debuggability without exposing the full key
    logger.debug("Using Gemini key ...%s", key[-4:])
    return key


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """
    Build and return a LangChain chat model.

    Parameters are resolved in order: explicit arg → env var → default.
    """
    provider = (provider or LLM_PROVIDER).lower().strip()
    temperature = temperature if temperature is not None else LLM_TEMPERATURE
    model = model or LLM_MODEL or DEFAULT_MODELS.get(provider, "")

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=OPENAI_API_KEY,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model,
            temperature=temperature,
            api_key=GROQ_API_KEY,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        chosen_key = get_next_gemini_key()
        # The google-genai SDK reads GOOGLE_API_KEY from env and ignores
        # the key passed to the constructor. Override it here.
        os.environ["GOOGLE_API_KEY"] = chosen_key
        os.environ["GEMINI_API_KEY"] = chosen_key
        logger.info(
            "Creating Gemini LLM (model=%s, key=...%s, pool_size=%d)",
            model, chosen_key[-4:], len(_GEMINI_KEY_POOL),
        )

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=chosen_key,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        "Supported: openai, groq, gemini"
    )
