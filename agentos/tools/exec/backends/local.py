import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

from agentos.tools.exec.backends.base import ExecutionBackend, ExecutionResult

logger = logging.getLogger(__name__)


class LocalBackend(ExecutionBackend):
    """Backend de ejecución local.
    
    Implementa la lógica original de RunCommandTool:
    - Ejecución directa con subprocess
    - Modo sandbox usando directorios temporales (tempdir isolation)
    """

    MAX_OUTPUT_BYTES = 10 * 1024  # 10KB

    def is_available(self) -> bool:
        return True

    def supports_command(self, command: str) -> bool:
        # El backend local soporta cualquier comando que el SO soporte
        return True

    def execute(
        self,
        command: str,
        args: List[str],
        cwd: str,
        timeout_s: int,
        env: Optional[Dict[str, str]] = None,
        sandbox: bool = False,
    ) -> ExecutionResult:
        start_time = time.time()
        
        try:
            if sandbox:
                result = self._execute_in_sandbox(command, args, timeout_s, env)
            else:
                result = self._execute_normal(command, args, cwd, timeout_s, env)
                
            duration_ms = int((time.time() - start_time) * 1000)
            
            return ExecutionResult(
                exit_code=result["exit_code"],
                stdout=result["stdout"],
                stderr=result["stderr"],
                timed_out=result["timed_out"],
                duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            # En caso de excepción no manejada, retornamos un resultado de error
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                timed_out=False,
                duration_ms=duration_ms
            )

    def _execute_normal(
        self,
        command: str,
        args: list[str],
        cwd: str,
        timeout_s: int,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """Ejecuta comando en modo normal (dentro del workspace)."""
        try:
            # Preparar env merging con el del sistema
            run_env = os.environ.copy()
            if env:
                run_env.update(env)

            # Ejecutar con shell=False (NUNCA shell=True)
            result = subprocess.run(
                [command] + args,
                cwd=cwd,
                capture_output=True,
                timeout=timeout_s,
                shell=False,  # CRÍTICO: nunca usar shell=True
                env=run_env
            )

            # Truncar output a 10KB
            stdout = result.stdout[: self.MAX_OUTPUT_BYTES].decode(
                "utf-8", errors="replace"
            )
            stderr = result.stderr[: self.MAX_OUTPUT_BYTES].decode(
                "utf-8", errors="replace"
            )

            return {
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timed_out": False,
            }

        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Comando excedió timeout de {timeout_s}s",
                "timed_out": True,
            }

    def _execute_in_sandbox(
        self, 
        command: str, 
        args: list[str], 
        timeout_s: int,
        env: Optional[Dict[str, str]] = None
    ) -> Dict:
        """Ejecuta comando en modo sandbox (tempdir isolation)."""
        sandbox_dir = None
        try:
            # Crear directorio temporal aislado
            sandbox_dir = tempfile.mkdtemp(prefix="agentos_sandbox_")

            # Limitar variables de entorno a mínimo
            # Si se pasó 'env', lo usamos, si no, construimos el default restringido
            if env is None:
                run_env = {
                    "PATH": os.environ.get("PATH", ""),
                    "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                    "TEMP": sandbox_dir,
                    "TMP": sandbox_dir,
                }
            else:
                run_env = env.copy()
                # Asegurar que TEMP/TMP apunten al sandbox si no se especificaron
                if "TEMP" not in run_env:
                    run_env["TEMP"] = sandbox_dir
                if "TMP" not in run_env:
                    run_env["TMP"] = sandbox_dir

            # Ejecutar con shell=False
            result = subprocess.run(
                [command] + args,
                cwd=sandbox_dir,
                env=run_env,
                capture_output=True,
                timeout=timeout_s,
                shell=False,  # CRÍTICO: nunca usar shell=True
            )

            # Truncar output a 10KB
            stdout = result.stdout[: self.MAX_OUTPUT_BYTES].decode(
                "utf-8", errors="replace"
            )
            stderr = result.stderr[: self.MAX_OUTPUT_BYTES].decode(
                "utf-8", errors="replace"
            )

            return {
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timed_out": False,
            }

        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Comando excedió timeout de {timeout_s}s",
                "timed_out": True,
            }

        finally:
            # Limpiar directorio temporal
            if sandbox_dir and Path(sandbox_dir).exists():
                try:
                    shutil.rmtree(sandbox_dir)
                except Exception as e:
                    logger.warning(
                        f"Error limpiando sandbox {sandbox_dir}: {e}"
                    )
