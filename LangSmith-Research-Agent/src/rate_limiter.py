"""
Rate-limited LLM wrapper for Gemini 2.5 Flash with API key rotation.

Designed for free-tier Google API keys to avoid 429 rate limit errors.
Demonstrates LangSmith metadata tracking for which API key is in use.
"""

import os
import time
import random
from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import traceable, get_current_run_tree


def _collect_api_keys() -> list[str]:
    """Collect all GOOGLE_API_KEY variants from environment."""
    keys = []
    # Primary key
    primary = os.getenv("GOOGLE_API_KEY")
    if primary:
        keys.append(primary)
    # Numbered variants: GOOGLE_API_KEY2, GOOGLE_API_KEY3, GOOGLE_API_KEY4, ...
    for i in range(2, 20):
        key = os.getenv(f"GOOGLE_API_KEY{i}")
        if key:
            keys.append(key)
    return keys


class RateLimitedLLM:
    """
    Wrapper around ChatGoogleGenerativeAI that provides:
    1. API key rotation across multiple GOOGLE_API_KEY* env vars
    2. Configurable delay between calls (default 5s)
    3. Exponential backoff with retry on 429 errors
    4. LangSmith metadata logging for the active API key index
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        temperature: float = 0,
        delay_seconds: float = 5.0,
        max_retries: int = 3,
    ):
        self.model = model
        self.temperature = temperature
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.api_keys = _collect_api_keys()
        self._current_key_index = 0
        self._last_call_time = 0.0

        if not self.api_keys:
            raise ValueError(
                "No GOOGLE_API_KEY found in environment. "
                "Set GOOGLE_API_KEY (and optionally GOOGLE_API_KEY2, GOOGLE_API_KEY3, ...) in your .env"
            )

        print(f"[RateLimitedLLM] Initialized with {len(self.api_keys)} API key(s), "
              f"delay={delay_seconds}s, max_retries={max_retries}")

    def _get_current_key(self) -> str:
        return self.api_keys[self._current_key_index]

    def _rotate_key(self):
        """Move to the next API key in the rotation."""
        if len(self.api_keys) > 1:
            old_index = self._current_key_index
            self._current_key_index = (self._current_key_index + 1) % len(self.api_keys)
            print(f"[RateLimitedLLM] Rotated API key: {old_index} → {self._current_key_index}")
        else:
            print("[RateLimitedLLM] Only 1 API key available, cannot rotate.")

    def _wait_for_rate_limit(self):
        """Enforce minimum delay between LLM calls."""
        elapsed = time.time() - self._last_call_time
        if elapsed < self.delay_seconds:
            wait_time = self.delay_seconds - elapsed
            print(f"[RateLimitedLLM] Waiting {wait_time:.1f}s for rate limit...")
            time.sleep(wait_time)

    def _create_llm(self) -> ChatGoogleGenerativeAI:
        """Create a fresh LLM instance with the current API key."""
        return ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self._get_current_key(),
            temperature=self.temperature,
            convert_system_message_to_human=True,
        )

    def invoke(self, messages: list, **kwargs) -> any:
        """
        Invoke the LLM with rate limiting, key rotation, and retry logic.
        
        Returns the LLM response on success.
        Raises the last exception if all retries are exhausted.
        """
        last_exception = None

        for attempt in range(self.max_retries):
            self._wait_for_rate_limit()

            try:
                llm = self._create_llm()
                self._last_call_time = time.time()
                
                # Log which key is being used via LangSmith metadata
                try:
                    run = get_current_run_tree()
                    if run:
                        run.metadata = run.metadata or {}
                        run.metadata["api_key_index"] = self._current_key_index
                        run.metadata["attempt"] = attempt + 1
                except Exception:
                    pass  # Not inside a traced context, skip

                response = llm.invoke(messages, **kwargs)
                return response

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                if "429" in error_str or "rate" in error_str or "quota" in error_str or "resource" in error_str:
                    # Rate limit hit — rotate key and backoff
                    backoff = (2 ** attempt) + random.uniform(1, 3)
                    print(f"[RateLimitedLLM] Rate limit hit (attempt {attempt + 1}/{self.max_retries}). "
                          f"Backing off {backoff:.1f}s...")
                    self._rotate_key()
                    time.sleep(backoff)
                else:
                    # Non-rate-limit error — re-raise immediately
                    raise

        raise last_exception
