"""Anthropic Claude LLM client with retry logic."""

from __future__ import annotations

import random
import time
from functools import wraps
from typing import Optional

from agentos.llm.base import LLMClient
from agentos.observability.logging import get_logger

RETRYABLE_STATUS = {429, 529, 408, 409, 500, 502, 503, 504}


def with_llm_retry(max_retries: int = 5):
    """Decorator that retries LLM calls on transient errors with exponential backoff."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_retries + 2):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    status = getattr(e, "status_code", None)
                    if isinstance(status, property):
                        status = None
                    try:
                        status = int(status)
                    except (TypeError, ValueError):
                        status = None
                    if status not in RETRYABLE_STATUS:
                        raise
                    if attempt > max_retries:
                        raise
                    retry_after = None
                    try:
                        retry_after = e.response.headers.get("retry-after")
                    except Exception:
                        pass
                    if retry_after:
                        delay = float(retry_after)
                    else:
                        base = min(0.5 * (2 ** (attempt - 1)), 32)
                        delay = base + random.random() * 0.25 * base
                    time.sleep(delay)
            raise last_error

        return wrapper

    return decorator


class AnthropicClient(LLMClient):
    """LLM client backed by Anthropic Claude API.

    Requires the ``anthropic`` package to be installed.
    The API key is read from the ``api_key`` argument or the
    ``ANTHROPIC_API_KEY`` environment variable (handled by the SDK).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.logger = get_logger("agentos")

    @with_llm_retry()
    def generate(self, prompt: str) -> str:
        """Generate text from a prompt using the Anthropic Messages API.

        Args:
            prompt: The input prompt.

        Returns:
            The generated text.

        Raises:
            ImportError: If the ``anthropic`` package is not installed.
            ValueError: If the API key is missing or the response is empty.
        """
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required. Install it with: pip install anthropic"
            ) from exc

        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.api_key:
            client = anthropic.Anthropic(api_key=self.api_key)
        else:
            client = anthropic.Anthropic()

        self.logger.info(
            "AnthropicClient.generate called",
            extra={"model": self.model, "prompt_len": len(prompt)},
        )

        response = client.messages.create(**kwargs)

        if not response.content:
            raise ValueError("Anthropic returned an empty response")

        text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )

        self.logger.info(
            "AnthropicClient.generate completed",
            extra={"model": self.model, "response_len": len(text)},
        )

        return text
