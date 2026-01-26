from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ExecutionResult:
    """Resultado de la ejecución de un comando."""
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: int


class ExecutionBackend(ABC):
    """Interfaz base para backends de ejecución."""

    @abstractmethod
    def execute(
        self,
        command: str,
        args: List[str],
        cwd: str,
        timeout_s: int,
        env: Optional[Dict[str, str]] = None,
        sandbox: bool = False,
    ) -> ExecutionResult:
        """Ejecuta un comando.

        Args:
            command: Comando a ejecutar
            args: Argumentos
            cwd: Directorio de trabajo (absoluto)
            timeout_s: Timeout en segundos
            env: Variables de entorno adicionales (opcional)
            sandbox: Si se debe aplicar aislamiento (tempdir o contenedor)

        Returns:
            ExecutionResult
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Verifica si el backend está disponible en el sistema actual."""
        pass

    @abstractmethod
    def supports_command(self, command: str) -> bool:
        """Verifica si el backend soporta un comando específico."""
        pass
