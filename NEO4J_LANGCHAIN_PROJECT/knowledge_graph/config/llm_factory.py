"""
Factory module for initializing LLMs and Embedding models.
Supports switching between OpenAI and Google Gemini based on environment variables.
"""

import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

from config.settings import LLM_MODEL, EMBEDDING_MODEL, LLM_MAX_TOKENS_PER_CALL


def get_llm(temperature: float = 0.0, **kwargs) -> BaseChatModel:
    """
    Returns an instantiated ChatModel based on the LLM_MODEL setting.
    If 'gemini' is in the model name, it returns ChatGoogleGenerativeAI.
    If 'llama', 'mixtral', or 'gemma' is in the model, it returns ChatGroq.
    Otherwise, it defaults to ChatOpenAI.
    """
    model_lower = LLM_MODEL.lower()
    if "gemini" in model_lower:
        # Requires GOOGLE_API_KEY in environment
        return ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            temperature=temperature,
            max_tokens=LLM_MAX_TOKENS_PER_CALL,
            **kwargs
        )
    elif any(keyword in model_lower for keyword in ["llama", "mixtral", "gemma"]):
        # Requires GROQ_API_KEY in environment
        return ChatGroq(
            model=LLM_MODEL,
            temperature=temperature,
            max_tokens=LLM_MAX_TOKENS_PER_CALL,
            **kwargs
        )
    else:
        # Requires OPENAI_API_KEY in environment
        return ChatOpenAI(
            model=LLM_MODEL,
            temperature=temperature,
            max_tokens=LLM_MAX_TOKENS_PER_CALL,
            **kwargs
        )


def get_llm_with_structured_output(schema: type[BaseModel], temperature: float = 0.0) -> callable:
    """
    Returns a runnable that forces the LLM to output the given Pydantic schema.
    Works for OpenAI, Gemini, and Groq natively.
    """
    llm = get_llm(temperature=temperature)
    return llm.with_structured_output(schema)


def get_embeddings(**kwargs) -> Embeddings:
    """
    Returns an instantiated Embeddings model based on the EMBEDDING_MODEL setting.
    If 'gemini' or 'gecko' is in the model name, it returns GoogleGenerativeAIEmbeddings.
    Otherwise, it defaults to OpenAIEmbeddings.
    """
    if "gemini" in EMBEDDING_MODEL.lower() or "gecko" in EMBEDDING_MODEL.lower():
        # Requires GOOGLE_API_KEY in environment
        # e.g., models/embedding-001 or text-embedding-004
        return GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            **kwargs
        )
    else:
        # Requires OPENAI_API_KEY in environment
        # e.g., text-embedding-3-small
        return OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            **kwargs
        )
