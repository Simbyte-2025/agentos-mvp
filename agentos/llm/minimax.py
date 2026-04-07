"""Minimax AI LLM client implementation."""

from __future__ import annotations

import json
import os
from typing import Optional

import httpx

from agentos.llm.base import LLMClient
from agentos.observability.logging import get_logger


class MinimaxClient(LLMClient):
    """Cliente para Minimax AI API.

    Configuración:
    - api_key: Token/API key de MiniMax (obligatorio para generate())
    - base_url: URL base Anthropic-compatible de la API
      (default: https://api.minimaxi.com/anthropic)
    - model: Modelo a usar (default: MiniMax-M2.7)
    - timeout: Timeout en segundos (default: 30)

    Nota: Si api_key es None, el cliente se puede instanciar pero generate()
    lanzará RuntimeError. Esto permite mantener la API viva y devolver
    errores controlados en /run.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.minimaxi.com/anthropic",
        model: str = "MiniMax-M2.7",
        timeout: int = 30,
    ):
        """Inicializar cliente Minimax.

        Args:
            api_key: Token/API key de MiniMax (puede ser None)
            base_url: URL base de la API Anthropic-compatible
            model: Modelo a usar
            timeout: Timeout en segundos
        """
        resolved_api_key = api_key or os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY")
        resolved_base_url = os.getenv("ANTHROPIC_BASE_URL", base_url)
        resolved_model = os.getenv("ANTHROPIC_MODEL", model)

        self.api_key = resolved_api_key
        self.base_url = resolved_base_url.rstrip("/")
        self.model = resolved_model
        self.timeout = timeout
        self.logger = get_logger("agentos")

    def generate(self, prompt: str) -> str:
        """Generar texto usando Minimax API (Anthropic-compatible).

        Args:
            prompt: Prompt de entrada

        Returns:
            Texto generado por el LLM

        Raises:
            RuntimeError: Si falta API key o hay error en la llamada
        """
        # Validar que tenemos API key
        if not self.api_key:
            raise RuntimeError(
                "No hay credencial MiniMax configurada. "
                "Configure MINIMAX_API_KEY o ANTHROPIC_AUTH_TOKEN para usar MiniMax."
            )

        # Construir URL del endpoint (Anthropic-compatible Messages API)
        url = f"{self.base_url}/v1/messages"

        # Headers (sin loggear el API key)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        
        # Body del request (Anthropic Messages API format)
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        }
                    ],
                }
            ],
        }
        
        # Log del request (sin API key)
        self.logger.debug(
            "Minimax API request (Anthropic-compatible)",
            extra={
                "url": url,
                "base_url": self.base_url,
                "model": self.model,
                "auth_scheme": "Bearer",
                "prompt_length": len(prompt),
            }
        )
        
        try:
            # Hacer request HTTP
            with httpx.Client(timeout=self.timeout, trust_env=False) as client:
                response = client.post(url, headers=headers, json=payload)
            
            # Capturar detalles para debug (antes de cualquier parsing)
            status_code = response.status_code
            content_type = response.headers.get("content-type", "unknown")
            body_raw = response.text
            body_truncated = body_raw[:800] if len(body_raw) > 800 else body_raw
            
            # Log si status no es 2xx (pero no lanzamos aún, intentamos parsear)
            if status_code < 200 or status_code >= 300:
                self.logger.error(
                    "Minimax API non-2xx response",
                    extra={
                        "status_code": status_code,
                        "content_type": content_type,
                        "body_truncated": body_truncated,
                    }
                )
            
            # Intentar parsear JSON
            try:
                data = response.json()
            except (json.JSONDecodeError, ValueError) as json_err:
                self.logger.error(
                    "Minimax API failed to parse JSON",
                    extra={
                        "status_code": status_code,
                        "content_type": content_type,
                        "body_truncated": body_truncated,
                        "json_error": str(json_err),
                    }
                )
                raise RuntimeError(
                    f"Minimax API retornó respuesta no-JSON (HTTP {status_code}). "
                    f"Content-Type: {content_type}. Body: {body_truncated[:200]}..."
                ) from json_err
            
            # Ahora sí, si status no es 2xx, levantar error con detalles
            if status_code < 200 or status_code >= 300:
                # Intentar extraer mensaje de error del JSON
                error_detail = data.get("error", {}).get("message") or data.get("message") or str(data)[:200]
                raise RuntimeError(f"Minimax API error (HTTP {status_code}): {error_detail}")
            
            # Verificar si hay error explícito en la respuesta
            if data.get("type") == "error":
                error_msg = data.get("error", {}).get("message", "Unknown error")
                self.logger.error(
                    "Minimax API error response",
                    extra={"error_type": data.get("error", {}).get("type"), "error_msg": error_msg}
                )
                raise RuntimeError(f"Minimax error: {error_msg}")
            
            # Verificar base_resp para errores lógicos (compatibilidad Minimax)
            if "base_resp" in data:
                base = data.get("base_resp", {})
                status_msg = base.get("status_msg")
                base_status_code = base.get("status_code")
                if status_msg and base_status_code != 0:
                    self.logger.error(
                        "Minimax API logical error",
                        extra={"status_msg": status_msg, "status_code": base_status_code}
                    )
                    raise RuntimeError(f"Minimax error: {status_msg} (status_code={base_status_code})")
            
            # Extraer contenido de la respuesta (Anthropic format)
            # Formato: {"content": [{"type": "text", "text": "..."}]}
            content_blocks = data.get("content", [])
            if not content_blocks:
                raise RuntimeError(
                    f"Minimax API response inválida: falta campo 'content'. Keys: {list(data.keys())}"
                )
            
            # Concatenar todos los bloques de texto
            text_parts = []
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            
            content = "".join(text_parts)
            
            if not content:
                raise RuntimeError(
                    f"Minimax API response inválida: no hay bloques de texto válidos. Content: {content_blocks}"
                )
            
            self.logger.debug(
                "Minimax API response received",
                extra={"response_length": len(content)}
            )
            
            return content
            
        except httpx.TimeoutException as e:
            self.logger.error(
                "Minimax API timeout",
                extra={"timeout": self.timeout, "error": str(e)}
            )
            raise RuntimeError(
                f"Minimax API timeout después de {self.timeout}s. "
                "Intente nuevamente o aumente el timeout."
            ) from e
            
        except httpx.HTTPStatusError as e:
            # Este bloque ya no debería ejecutarse porque quitamos raise_for_status()
            # pero lo mantenemos por si httpx lanza de otra forma
            resp_status = e.response.status_code
            self.logger.error(
                "Minimax API HTTP error",
                extra={"status_code": resp_status, "error": str(e)}
            )
            raise RuntimeError(f"Minimax API error (HTTP {resp_status})") from e
            
        except RuntimeError:
            # Re-raise RuntimeError sin wrap adicional
            raise
            
        except Exception as e:
            self.logger.error(
                "Minimax API error inesperado",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            self.logger.error(f"Minimax API error details -> type: {type(e).__name__}, msg: {str(e)}")
            raise RuntimeError(f"Minimax API error inesperado: {e}") from e

