"""Anthropic Claude LLM client with robust retry logic.

Refactored to:
- Reuse the anthropic.Anthropic() client instance (not per-call)
- Use the centralized retry engine (llm/retry.py)
- Support fallback_model and abort_event
- Use structured errors from agentos.errors
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from agentos.errors import AuthenticationError, ConfigurationError
from agentos.llm.base import LLMClient
from agentos.llm.cache import PromptCache
from agentos.llm.retry import RetryPolicy, RetryState, retry_llm_call
from agentos.observability.logging import get_logger


class AnthropicClient(LLMClient):
    """Cliente para Anthropic Claude API.

    Mejoras vs MVP anterior:
    - Reutiliza instancia de ``anthropic.Anthropic`` (no crea por llamada)
    - Retry centralizado con ``RetryPolicy`` y ``RetryState``
    - Soporte de ``fallback_model`` y ``abort_event``
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        timeout: int = 60,
        fallback_model: Optional[str] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.fallback_model = fallback_model
        self.retry_policy = retry_policy or RetryPolicy()
        self.retry_state = RetryState()
        self.cache = PromptCache()
        self.logger = get_logger("agentos")
        self._client = None  # Lazy-initialized, reused

    def _get_client(self):
        """Get or create the anthropic client (singleton per AnthropicClient)."""
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise AuthenticationError(
                "ANTHROPIC_API_KEY no configurada. "
                "Configure la variable de entorno ANTHROPIC_API_KEY para usar Anthropic."
            )
        try:
            import anthropic
        except ImportError as e:
            raise ConfigurationError(
                "Paquete 'anthropic' no instalado. Ejecute: pip install anthropic"
            ) from e

        kwargs = {"api_key": self.api_key, "timeout": self.timeout}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def _resolve_model(self) -> str:
        """Return fallback model if consecutive failures exceed threshold."""
        if (
            self.fallback_model
            and self.retry_state.consecutive_failures >= self.retry_policy.fallback_after_consecutive
        ):
            self.logger.warning(
                "Switching to fallback model",
                extra={
                    "primary_model": self.model,
                    "fallback_model": self.fallback_model,
                    "consecutive_failures": self.retry_state.consecutive_failures,
                },
            )
            return self.fallback_model
        return self.model

    def _do_generate(self, prompt: str, model: str) -> str:
        """Single API call without retry (retry is handled by caller)."""
        client = self._get_client()

        self.logger.debug(
            "Anthropic API request",
            extra={"model": model, "prompt_length": len(prompt), "max_tokens": self.max_tokens},
        )

        message = client.messages.create(
            model=model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        content_blocks = message.content
        if not content_blocks:
            raise RuntimeError("Anthropic API response inválida: sin bloques de contenido.")

        text_parts = [block.text for block in content_blocks if hasattr(block, "text")]
        content = "".join(text_parts)

        if not content:
            raise RuntimeError(
                f"Anthropic API response inválida: sin texto. stop_reason={message.stop_reason}"
            )

        self.logger.debug(
            "Anthropic API response received",
            extra={
                "response_length": len(content),
                "stop_reason": message.stop_reason,
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
        )
        return content

    def generate(
        self,
        prompt: str,
        abort_event: Optional[threading.Event] = None,
        use_cache: bool = True,
    ) -> str:
        """Generate text with retry, fallback model, cache, and abort support."""
        # Check local cache first
        if use_cache:
            cached = self.cache.get(prompt)
            if cached is not None:
                return cached

        model = self._resolve_model()

        result = retry_llm_call(
            self._do_generate,
            prompt,
            model,
            policy=self.retry_policy,
            abort_event=abort_event,
            retry_state=self.retry_state,
        )

        if use_cache:
            self.cache.put(prompt, result)

        return result
