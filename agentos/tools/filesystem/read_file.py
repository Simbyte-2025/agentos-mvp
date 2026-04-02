from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from ..base import BaseTool, ToolInput, ToolOutput, ValidationResult

DANGEROUS_PATTERNS = [
    ".env",
    ".bashrc",
    ".gitconfig",
    ".gitcredentials",
    "secrets/",
    "credentials",
    ".ssh/",
    "id_rsa",
    "id_ed25519",
    ".claude.json",
    ".mcp.json",
]


class ReadFileTool(BaseTool):
    """Lee un archivo desde un workspace permitido.

    Payload:
      - path: str
      - max_bytes: int (opcional)
    """

    def __init__(self, workspace_root: str | Path | None = None):
        root = Path(workspace_root or os.getenv("AGENTOS_WORKSPACE_ROOT", ".")).resolve()
        self.workspace_root = root
        super().__init__(name="read_file", description="Lee un archivo dentro del workspace permitido.", risk="read")

    def validate(self, tool_input) -> ValidationResult:
        path = ""
        if hasattr(tool_input, "payload"):
            path = tool_input.payload.get("path", "")
        elif isinstance(tool_input, dict):
            path = tool_input.get("path", "")
        path_lower = path.lower().replace("\\", "/")
        for pattern in DANGEROUS_PATTERNS:
            if pattern in path_lower:
                return ValidationResult(
                    valid=False,
                    error=f"Acceso bloqueado a path sensible: {path}",
                    behavior="deny",
                )
        return super().validate(tool_input)

    def execute(self, tool_input: ToolInput) -> ToolOutput:
        validation = self.validate(tool_input)
        if not validation.valid:
            return ToolOutput(success=False, error=validation.error)

        try:
            rel_path = str(tool_input.payload.get("path", ""))
            if not rel_path:
                return ToolOutput(success=False, error="payload.path es requerido")

            max_bytes = int(tool_input.payload.get("max_bytes", 200_000))
            target = (self.workspace_root / rel_path).resolve()

            # Prevenir path traversal
            if not str(target).startswith(str(self.workspace_root)):
                return ToolOutput(success=False, error="Acceso fuera del workspace no permitido")

            if not target.exists() or not target.is_file():
                return ToolOutput(success=False, error=f"Archivo no encontrado: {rel_path}")

            data = target.read_bytes()[:max_bytes]
            text = data.decode("utf-8", errors="replace")
            return ToolOutput(success=True, data={"path": rel_path, "content": text, "truncated": len(data) >= max_bytes})
        except Exception as e:
            return ToolOutput(success=False, error=str(e))
