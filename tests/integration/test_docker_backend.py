import os
import shutil
import pytest
from pathlib import Path

from agentos.tools.exec.backends.docker import DockerBackend
from agentos.tools.exec.run_command import RunCommandTool
from agentos.tools.base import ToolInput

# Definir ruta para workspace interno
INTERNAL_WORKSPACE_ROOT = Path(__file__).parent.parent / ".tmp_docker_workspace"

@pytest.fixture
def internal_workspace():
    """Crea y limpia un workspace dentro del árbol del proyecto."""
    if INTERNAL_WORKSPACE_ROOT.exists():
        shutil.rmtree(INTERNAL_WORKSPACE_ROOT)
    
    INTERNAL_WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    
    yield INTERNAL_WORKSPACE_ROOT
    
    # Limpieza final
    if INTERNAL_WORKSPACE_ROOT.exists():
        shutil.rmtree(INTERNAL_WORKSPACE_ROOT)

@pytest.mark.skipif(
    not DockerBackend().is_available(),
    reason="Docker no disponible o no accesible"
)
def test_docker_backend_executes_python_script(internal_workspace, monkeypatch):
    """Test de integración: ejecutar script python básico en contenedor."""
    
    # Configurar backend Docker
    monkeypatch.setenv("AGENTOS_EXEC_BACKEND", "docker")
    
    # Crear un script simple dentro del workspace
    hello_file = internal_workspace / "hello.py"
    hello_file.write_text("print('hello-docker-backend')", encoding="utf-8")
    
    # Instanciar herramienta apuntando al workspace interno
    tool = RunCommandTool(workspace_root=internal_workspace)
    
    # Verificar que se seleccionó DockerBackend
    assert isinstance(tool.backend, DockerBackend)
    
    # Ejecutar python script
    result = tool.execute(ToolInput(
        request_id="docker_int_test",
        payload={
            "command": "python",
            "args": ["hello.py"],
            "timeout_s": 60
        }
    ))
    
    # Verificar éxito
    assert result.success is True
    assert result.data["exit_code"] == 0
    assert "hello-docker-backend" in result.data["stdout"]
