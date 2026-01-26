import logging
import subprocess
import time
import uuid
from typing import Dict, List, Optional

from agentos.tools.exec.backends.base import ExecutionBackend, ExecutionResult

logger = logging.getLogger(__name__)


class DockerBackend(ExecutionBackend):
    """Backend de ejecución que utiliza Docker para aislamiento real.

    Características:
    - Aislamiento real (fs, network, resources).
    - Timeout determinista con limpieza de contenedores.
    - Soporte best-effort para usuarios no-root en Windows.
    """

    SUPPORTED_COMMANDS = ["python", "pytest"]
    MAX_OUTPUT_BYTES = 10 * 1024  # 10KB

    def __init__(self, image: str = "python:3.11-slim"):
        self.image = image

    def is_available(self) -> bool:
        """Verifica si Docker está disponible usando 'docker info'."""
        try:
            subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
                check=True  # check=True lanza excecipn si exit_code != 0
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def supports_command(self, command: str) -> bool:
        """Verifica si el backend soporta el comando (solo multiplataforma)."""
        return command in self.SUPPORTED_COMMANDS

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
        container_name = f"agentos-runcommand-{str(uuid.uuid4())[:8]}"

        try:
            # Intentar ejecutar con usuario restringido (best-effort)
            try:
                result = self._run_docker_command(
                    container_name, command, args, cwd, timeout_s, env, use_user_flag=True
                )
            except Exception as e:
                # Si falla y parece ser un problema de permisos/docker, reintentar sin user flag
                # Detectar errores comunes de Windows/Docker montura es difícil solo con excepción,
                # pero asumiendo que el comando base es válido, el fallo suele ser runtime de docker.
                # Simplificación: si falla con exit code > 0 o error de docker, probamos fallback.
                # Aquí asumimos que _run_docker_command lanza excepción o devuelve exit_code != 0 
                # si falla el arranque. Pero _run_docker_command devuelve un dict.
                # Revisemos el result, si exit_code es 125/126/127 podrías ser docker fail, 
                # pero también fallo del comando.
                # Para MVP seguro: si _run_docker_command lanza excepción (ej: docker run falla launch), catch.
                # Si retorna exit_code, es que corrió.
                # El requerimiento dice: "Si falla por permisos/mount" -> esto suele salir en stderr del docker run.
                # Vamos a capturar el resultado primero.
                raise e

            # Analizar si falló por permisos de usuario (workaround para Windows)
            # Docker suele devolver 125/126/127 si falla al iniciar container o permisos.
            # O si stderr contiene "permission denied" antes de ejecutar el comando.
            # Una heurística simple para este MVP: si stderr tiene mensajes clave de docker.
            
            # Mejor enfoque según requerimiento: Intentar con user, si falla (excepción o stderr especifico), reintentar.
            # Dado que subprocess.run captura output, si docker run falla al montar, devuelve exit code != 0 y stderr.
            # Vamos a refactorizar ligeramente para permitir el reintento explícito si se detecta fallo de arranque.
            
            # En realidad, si 'docker run' falla por permisos de montaje, el exit code no es el del comando, 
            # sino del engine.
            
            # Implementación robusta:
            # 1. Ejecutar.
            # 2. Si exit_code != 0 y stderr sugiere error de permisos/mount Y usamos user flag -> reintentar.
            
            # Heurística para reintento:
            # - exit_code != 0
            # - stderr contiene "permission denied" o "mount" o "access denied"
            if result["exit_code"] != 0 and self._is_permission_error(result["stderr"]):
                logger.warning(
                    f"[{container_name}] Fallo de permisos con --user, reintentando como root (best-effort Windows)",
                    extra={"stderr": result["stderr"]}
                )
                result = self._run_docker_command(
                    container_name, command, args, cwd, timeout_s, env, use_user_flag=False
                )

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
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Error interno DockerBackend: {str(e)}",
                timed_out=False,
                duration_ms=duration_ms
            )
        finally:
            # Asegurar limpieza del contenedor (redundancia por seguridad)
            self._cleanup_container(container_name)

    def _run_docker_command(
        self,
        container_name: str,
        command: str,
        args: List[str],
        cwd: str,
        timeout_s: int,
        env: Optional[Dict[str, str]],
        use_user_flag: bool
    ) -> Dict:
        """Construye y ejecuta el comando docker run."""
        
        # Construcción del comando
        docker_cmd = [
            "docker", "run",
            "--rm",
            "--name", container_name,
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",
            "--network=none",
            "--memory=512m",
            "--cpus=1.0",
        ]

        if use_user_flag:
            docker_cmd.append("--user=1000:1000")

        # Variables de entorno
        if env:
            for k, v in env.items():
                docker_cmd.extend(["-e", f"{k}={v}"])

        # Montaje de workspace (siempre se usa cwd para montar workspace)
        # Nota: Asumimos que cwd está dentro del workspace o es el workspace.
        # En la implementación actual de run_command, cwd es ruta absoluta.
        # Necesitamos montar el directorio padre relevante o el workspace root.
        # DockerBackend no recibe workspace_root explicito aquí, pero cwd es absoluto.
        # Para simplificar y asegurar compatibilidad, montamos cwd como /workspace.
        # Esto funciona si el comando se ejecuta en la raíz del proyecto.
        # Si cwd es un subdirectorio, podría ser confuso.
        # Asunción segura MVP: montamos cwd -> /workspace y relative args funcionan.
        # PERO: agentos run_command puede recibir cwd relativo que run_command resuelve a absoluto.
        # Vamos a montar 'cwd' (ruta local absoluta) en '/workspace'.
        
        # Corrección para paths en Windows (ej: C:\Users... -> /c/Users...) si fuera necesario para cygwin/bash,
        # pero Docker Desktop for Windows maneja paths estilo Windows (C:\...) correctamente en volumenes -v.
        docker_cmd.extend([
            "-v", f"{cwd}:/workspace:rw",  # RW para soportar .pytest_cache
            "-w", "/workspace"
        ])

        docker_cmd.append(self.image)
        docker_cmd.append(command)
        docker_cmd.extend(args)

        try:
            # Ejecutar con subprocess.run para timeout
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                timeout=timeout_s,
                text=False, # Manejo manual de decoding
                check=False
            )

            stdout = result.stdout[:self.MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
            stderr = result.stderr[:self.MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")

            return {
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timed_out": False
            }

        except subprocess.TimeoutExpired:
            # Timeout determinista: matar contenedor
            self._cleanup_container(container_name)
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Comando excedió timeout de {timeout_s}s (contenedor eliminado)",
                "timed_out": True
            }

    def _cleanup_container(self, container_name: str):
        """Mata y elimina el contenedor por nombre."""
        try:
            subprocess.run(
                ["docker", "kill", container_name],
                capture_output=True,
                check=False
            )
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                check=False
            )
        except Exception as e:
            logger.warning(f"Error limpiando contenedor {container_name}: {e}")

    def _is_permission_error(self, stderr: str) -> bool:
        """Heurística para detectar errores de permisos de Docker en Windows."""
        keywords = ["permission denied", "access denied", "mkdir", "touch"]
        return any(k in stderr.lower() for k in keywords)
