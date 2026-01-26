from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from agentos.security.run_command_allowlist import CommandAllowlist
from agentos.tools.exec.backends.docker import DockerBackend
from agentos.tools.exec.backends.local import LocalBackend

from ..base import BaseTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


class RunCommandTool(BaseTool):
    """Ejecuta comandos del sistema con seguridad estricta.

    Capas de seguridad:
    1. Allowlist estricta de comandos
    2. Bloqueo de operadores shell
    3. shell=False obligatorio
    4. Validación de path traversal
    5. Timeout estricto
    6. Modo sandbox (tempdir isolation)
    7. Permisos explícitos (risk: execute)
    8. Validación de args específica por comando

    Payload:
      - command: str (requerido)
      - args: list[str] (opcional)
      - cwd: str (opcional, relativo al workspace)
      - timeout_s: int (opcional, default: 30, max: 300)
      - sandbox: bool (opcional, default: False)
      - env: dict[str, str] (opcional)

    Output:
      - exit_code: int
      - stdout: str (truncado a 10KB)
      - stderr: str (truncado a 10KB)
      - timed_out: bool
      - command_executed: str (para auditoría)
    """

    MAX_OUTPUT_BYTES = 10 * 1024  # 10KB
    MAX_LOG_CHARS = 1000  # Truncar output en logs

    def __init__(
        self,
        workspace_root: Optional[str | Path] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Inicializa RunCommandTool.

        Args:
            workspace_root: Raíz del workspace (default: AGENTOS_WORKSPACE_ROOT env)
            config: Configuración con allowed_commands, max_timeout_s, etc.
        """
        self.workspace_root = Path(
            workspace_root or os.getenv("AGENTOS_WORKSPACE_ROOT", ".")
        ).resolve()
        self.config = config or {}

        # Configuración de timeouts
        self.default_timeout_s = self.config.get("default_timeout_s", 30)
        self.max_timeout_s = self.config.get("max_timeout_s", 300)

        # Inicializar allowlist
        self.allowlist = CommandAllowlist(config=self.config)

        # Inicializar backend segun AGENTOS_EXEC_BACKEND
        self._initialize_backend()

        super().__init__(
            name="run_command",
            description="Ejecuta comandos del sistema con allowlist estricta y modo sandbox.",
            risk="execute",
        )

    def _initialize_backend(self):
        """Inicializa self.backend basado en AGENTOS_EXEC_BACKEND y disponibilidad."""
        backend_type = os.getenv("AGENTOS_EXEC_BACKEND", "local").lower()
        
        if backend_type == "docker":
            docker_backend = DockerBackend()
            if docker_backend.is_available():
                self.backend = docker_backend
                logger.info("Usando DockerBackend para run_command")
            else:
                self.backend = LocalBackend()
                logger.warning("DockerBackend no disponible (docker info falló). Usando fallback a LocalBackend.")
        elif backend_type == "local":
            self.backend = LocalBackend()
        else:
            self.backend = LocalBackend()
            logger.warning(f"Backend desconocido '{backend_type}'. Usando fallback a LocalBackend.")

    def execute(self, tool_input: ToolInput) -> ToolOutput:
        """Ejecuta comando con validación de seguridad estricta."""
        start_time = time.time()
        request_id = tool_input.request_id
        payload = tool_input.payload

        try:
            # Extraer y validar inputs
            command = payload.get("command", "").strip()
            if not command:
                return ToolOutput(
                    success=False, error="payload.command es requerido", meta={}
                )

            args = payload.get("args", [])
            if not isinstance(args, list):
                return ToolOutput(
                    success=False, error="payload.args debe ser una lista", meta={}
                )

            cwd = payload.get("cwd", ".")
            timeout_s = min(
                int(payload.get("timeout_s", self.default_timeout_s)), self.max_timeout_s
            )
            sandbox = bool(payload.get("sandbox", False))
            env = payload.get("env", {})

            # 1. Validar contra allowlist (incluye validación de Python args)
            allowlist_decision = self.allowlist.validate(command, args)
            if not allowlist_decision.allowed:
                logger.warning(
                    f"[{request_id}] Comando bloqueado por allowlist: {command} {args}",
                    extra={
                        "request_id": request_id,
                        "tool": "run_command",
                        "command": command,
                        "command_args": args,
                        "reason": allowlist_decision.reason,
                    },
                )
                return ToolOutput(
                    success=False, error=allowlist_decision.reason, meta={}
                )

            # 2. Validar cwd contra path traversal
            cwd_abs_path_str = ""
            if not sandbox:  # En sandbox, cwd es ignorado por el backend o manejado internamente
                cwd_path = (self.workspace_root / cwd).resolve()
                if not str(cwd_path).startswith(str(self.workspace_root)):
                    return ToolOutput(
                        success=False,
                        error="cwd fuera del workspace no permitido",
                        meta={},
                    )
                cwd_abs_path_str = str(cwd_path)
            else:
                cwd_abs_path_str = ""  # Backend manejará el directorio sandbox

            # 3. Selección dinámica de backend si el comando no es soportado
            # Si el backend actual (ej: Docker) no soporta el comando (ej: dir), usamos fallback temporal a Local
            # sin cambiar self.backend permanentemente.
            current_backend = self.backend
            if not current_backend.supports_command(command):
                logger.warning(
                    f"[{request_id}] Comando '{command}' no soportado por {type(current_backend).__name__}. "
                    f"Usando fallback temporal a LocalBackend."
                )
                current_backend = LocalBackend()

            # 4. Delegar ejecución al backend
            result = current_backend.execute(
                command=command,
                args=args,
                cwd=cwd_abs_path_str,
                timeout_s=timeout_s,
                env=env,
                sandbox=sandbox,
            )

            # Log estructurado (output truncado)
            command_executed_str = f"{command} {' '.join(args)}"
            if sandbox:
                command_executed_str += " (sandbox)"

            logger.info(
                f"[{request_id}] Comando ejecutado: {command}",
                extra={
                    "request_id": request_id,
                    "tool": "run_command",
                    "command": command,
                    "command_args": args,
                    "exit_code": result.exit_code,
                    "duration_ms": result.duration_ms,
                    "sandbox": sandbox,
                    "timed_out": result.timed_out,
                    "stdout_length": len(result.stdout),
                    "stderr_length": len(result.stderr),
                },
            )

            # Mapear ExecutionResult a dict compatible con ToolOutput existente
            result_data = {
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": result.timed_out,
                "command_executed": command_executed_str,
            }

            return ToolOutput(
                success=True,
                data=result_data,
                meta={"duration_ms": result.duration_ms, "sandbox": sandbox},
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"[{request_id}] Error ejecutando comando: {e}",
                extra={
                    "request_id": request_id,
                    "tool": "run_command",
                    "error": str(e),
                    "duration_ms": duration_ms,
                },
                exc_info=True,
            )
            return ToolOutput(success=False, error=str(e), meta={})
