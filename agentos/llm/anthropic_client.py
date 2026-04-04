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
                    try:
                        status = int(status)
                    except (TypeError, ValueError):
                        status = None
                    if status not in RETRYABLE_STATUS:
                        raise
                    if attempt > max_retries:
                        raise last_error
                    retry_after = None
                    try:
                        retry_after = e.response.headers.get("retry-after")
                    except (AttributeError, TypeError, ValueError):
                        pass
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except (TypeError, ValueError):
                            delay = None
                    else:
                        delay = None
                    if not delay:
                        base = min(0.5 * (2 ** (attempt - 1)), 32)
                        delay = base + random.random() * 0.25 * base
                    time.sleep(delay)
            raise last_error

        return wrapper

    return decorator


class AnthropicClient(LLMClient):
    """Cliente para Anthropic Claude API.

    Configuración:
    - api_key: API key de Anthropic (obligatorio para generate())
    - model: Modelo a usar (default: claude-sonnet-4-6)
    - max_tokens: Máximo de tokens en la respuesta (default: 4096)
    - timeout: Timeout en segundos (default: 60)

    Nota: Si api_key es None, el cliente se puede instanciar pero generate()
    lanzará RuntimeError. Esto permite mantener la API viva y devolver
    errores controlados en /run.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        timeout: int = 60,
    ):
        """Inicializar cliente Anthropic.

        Args:
            api_key: API key de Anthropic (puede ser None)
            model: Modelo a usar
            max_tokens: Máximo de tokens en la respuesta
            timeout: Timeout en segundos
        """
        import os
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.logger = get_logger("agentos")

    @with_llm_retry()
    def generate(self, prompt: str) -> str:
        """Generar texto usando Anthropic Claude API.

        Args:
            prompt: Prompt de entrada

        Returns:
            Texto generado por el LLM

        Raises:
            RuntimeError: Si falta API key o hay error en la llamada
        """
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY no configurada. "
                "Configure la variable de entorno ANTHROPIC_API_KEY para usar Anthropic."
            )

        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                "Paquete 'anthropic' no instalado. Ejecute: pip install anthropic"
            ) from e

        self.logger.debug(
            "Anthropic API request",
            extra={
                "model": self.model,
                "prompt_length": len(prompt),
                "max_tokens": self.max_tokens,
            },
        )

        try:
            kwargs = {"api_key": self.api_key, "timeout": self.timeout}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            client = anthropic.Anthropic(**kwargs)

            message = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )

            content_blocks = message.content
            if not content_blocks:
                raise RuntimeError(
                    "Anthropic API response inválida: sin bloques de contenido."
                )

            text_parts = [
                block.text
                for block in content_blocks
                if hasattr(block, "text")
            ]
            content = "".join(text_parts)

            if not content:
                raise RuntimeError(
                    f"Anthropic API response inválida: sin texto. "
                    f"stop_reason={message.stop_reason}"
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

        except RuntimeError:
            raise

        except Exception as e:
            self.logger.error(
                "Anthropic API error inesperado",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            raise RuntimeError(f"Anthropic API error inesperado: {e}") from e
