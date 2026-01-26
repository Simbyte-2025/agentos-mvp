from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AllowlistDecision:
    """Resultado de validación de allowlist."""

    allowed: bool
    reason: str


class CommandAllowlist:
    """Valida comandos contra allowlist estricta con validación específica por comando.

    Capas de seguridad:
    1. Comando debe estar en allowlist
    2. Bloqueo de operadores shell peligrosos
    3. Validación específica de args por comando (ej: Python -c, -m, -)
    """

    # Operadores shell peligrosos que permiten inyección
    # Nota: NO incluir paréntesis - causan falsos positivos en rutas como "Program Files (x86)"
    DANGEROUS_TOKENS = ["&&", "||", ";", "|", ">", "<", "$", "`"]

    # Args peligrosos específicos para Python
    PYTHON_DANGEROUS_ARGS = ["-c", "-m", "-"]

    def __init__(
        self,
        allowed_commands: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Inicializa allowlist desde config o variable de entorno.

        Args:
            allowed_commands: Lista de comandos permitidos (override directo)
            config: Diccionario de configuración con 'allowed_commands'
        """
        if allowed_commands:
            self.allowed_commands = allowed_commands
        elif config and "allowed_commands" in config:
            self.allowed_commands = config["allowed_commands"]
        else:
            # Cargar desde ENV o usar default
            env_commands = os.getenv("AGENTOS_ALLOWED_COMMANDS", "")
            if env_commands:
                self.allowed_commands = [
                    cmd.strip() for cmd in env_commands.split(",") if cmd.strip()
                ]
            else:
                # Default: solo comandos básicos de lectura
                self.allowed_commands = ["python", "pytest", "dir", "type"]

    def validate(
        self, command: str, args: Optional[List[str]] = None
    ) -> AllowlistDecision:
        """Valida comando y args contra allowlist y reglas de seguridad.

        Args:
            command: Comando base a ejecutar
            args: Argumentos del comando

        Returns:
            AllowlistDecision con allowed=True si pasa todas las validaciones
        """
        args = args or []

        # 1. Validar que comando esté en allowlist
        if command not in self.allowed_commands:
            return AllowlistDecision(
                allowed=False,
                reason=f"Comando '{command}' no está en allowlist. Permitidos: {', '.join(self.allowed_commands)}",
            )

        # 2. Bloquear operadores shell en command
        if self._contains_shell_operators(command):
            for token in self.DANGEROUS_TOKENS:
                if token in command:
                    return AllowlistDecision(
                        allowed=False,
                        reason=f"Operador shell peligroso detectado en comando: '{token}'",
                    )

        # 3. Bloquear operadores shell en args
        for arg in args:
            if self._contains_shell_operators(arg):
                for token in self.DANGEROUS_TOKENS:
                    if token in arg:
                        return AllowlistDecision(
                            allowed=False,
                            reason=f"Operador shell peligroso detectado en arg: '{token}'",
                        )

        # 4. Validación específica por comando
        if command == "python":
            python_validation = self._validate_python_args(args)
            if not python_validation.allowed:
                return python_validation

        return AllowlistDecision(allowed=True, reason="Permitido")

    def _contains_shell_operators(self, text: str) -> bool:
        """Detecta si el texto contiene operadores shell peligrosos."""
        return any(token in text for token in self.DANGEROUS_TOKENS)

    def _validate_python_args(self, args: List[str]) -> AllowlistDecision:
        """Valida args específicos para Python.

        Bloquea:
        - `-c`: Ejecutar código inline
        - `-m`: Ejecutar módulo
        - `-`: Leer código desde stdin

        Permite:
        - `--version`, `--help`: Información
        - `<script.py>`: Ejecutar script (validado por path traversal en RunCommandTool)
        """
        for arg in args:
            if arg in self.PYTHON_DANGEROUS_ARGS:
                return AllowlistDecision(
                    allowed=False,
                    reason=f"Python arg peligroso bloqueado: '{arg}'. Solo se permite ejecutar scripts o --version/--help.",
                )
        return AllowlistDecision(allowed=True, reason="Python args permitidos")
