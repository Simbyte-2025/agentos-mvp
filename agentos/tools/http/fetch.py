from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from ..base import BaseTool, ToolInput, ToolOutput


class HttpFetchTool(BaseTool):
    """HTTP GET con timeout.

    Payload:
      - url: str
      - timeout_s: float (opcional)

    Opcional: allowlist de dominios via AGENTOS_HTTP_ALLOWLIST (coma-separado).
    """

    def __init__(self):
        super().__init__(name="http_fetch", description="Realiza una petición HTTP GET con timeout y manejo de errores.", risk="read")
        raw = os.getenv("AGENTOS_HTTP_ALLOWLIST", "").strip()
        self.allowlist = [d.strip() for d in raw.split(",") if d.strip()]

    def execute(self, tool_input: ToolInput) -> ToolOutput:
        url = str(tool_input.payload.get("url", "")).strip()
        if not url:
            return ToolOutput(success=False, error="payload.url es requerido")

        if self.allowlist:
            domain = urlparse(url).netloc
            if domain not in self.allowlist:
                return ToolOutput(success=False, error=f"Dominio no permitido: {domain}")

        timeout_s = float(tool_input.payload.get("timeout_s", 15.0))
        try:
            with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
                r = client.get(url)
                r.raise_for_status()
                content_type = r.headers.get("content-type", "")
                text = r.text
                # Evitar respuestas enormes en contexto
                if len(text) > 50_000:
                    text = text[:50_000]
                    truncated = True
                else:
                    truncated = False

            return ToolOutput(success=True, data={"url": url, "status": r.status_code, "content_type": content_type, "text": text, "truncated": truncated})
        except Exception as e:
            return ToolOutput(success=False, error=str(e))
