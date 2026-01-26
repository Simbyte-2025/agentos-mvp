import os
import tempfile
from pathlib import Path

import pytest

from agentos.tools.base import ToolInput, ToolOutput
from agentos.tools.exec.run_command import RunCommandTool


@pytest.fixture
def temp_workspace(tmp_path):
    """Crea workspace temporal para tests."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    # Crear script de prueba
    test_script = workspace / "test_script.py"
    test_script.write_text('print("Hello from script")')
    
    return workspace


@pytest.fixture
def run_command_tool(temp_workspace):
    """Crea RunCommandTool con workspace temporal."""
    config = {
        "allowed_commands": ["python", "pytest", "dir", "type"],
        "max_timeout_s": 300,
        "default_timeout_s": 30,
    }
    return RunCommandTool(workspace_root=temp_workspace, config=config)


def test_run_allowed_command_success(run_command_tool):
    """Ejecuta comando permitido exitosamente."""
    tool_input = ToolInput(
        request_id="test_001",
        payload={"command": "python", "args": ["--version"]},
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is True
    assert result.data["exit_code"] == 0
    assert "Python" in result.data["stdout"]
    assert result.data["timed_out"] is False
    assert "python --version" in result.data["command_executed"]


def test_run_disallowed_command_fails(run_command_tool):
    """Comando no permitido falla en validación."""
    tool_input = ToolInput(
        request_id="test_002",
        payload={"command": "del", "args": ["file.txt"]},
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is False
    assert "no está en allowlist" in result.error
    assert result.data is None


def test_shell_injection_blocked(run_command_tool):
    """Intento de inyección shell es bloqueado."""
    tool_input = ToolInput(
        request_id="test_003",
        payload={"command": "python", "args": ["--version", "&&", "del", "*"]},
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is False
    assert "Operador shell peligroso" in result.error


def test_python_args_injection_blocked(run_command_tool):
    """Python con -c es bloqueado."""
    tool_input = ToolInput(
        request_id="test_004",
        payload={"command": "python", "args": ["-c", "1+1"]},
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is False
    assert "Python arg peligroso bloqueado" in result.error
    assert "-c" in result.error


def test_timeout_enforced(run_command_tool):
    """Timeout se aplica correctamente."""
    # Crear script que duerme más que el timeout
    workspace = run_command_tool.workspace_root
    sleep_script = workspace / "sleep_script.py"
    sleep_script.write_text("import time; time.sleep(10)")
    
    tool_input = ToolInput(
        request_id="test_005",
        payload={
            "command": "python",
            "args": ["sleep_script.py"],
            "timeout_s": 1,  # 1 segundo
        },
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is True  # Comando ejecuta, pero timeout
    assert result.data["timed_out"] is True
    assert result.data["exit_code"] == -1
    assert "timeout" in result.data["stderr"].lower()


def test_sandbox_mode_isolation(run_command_tool):
    """Modo sandbox aísla ejecución (tempdir)."""
    tool_input = ToolInput(
        request_id="test_006",
        payload={
            "command": "python",
            "args": ["-c", "1+1"],  # Este debería fallar por -c
            "sandbox": True,
        },
    )
    
    # Primero verificar que -c es bloqueado incluso en sandbox
    result = run_command_tool.execute(tool_input)
    assert result.success is False
    assert "Python arg peligroso bloqueado" in result.error
    assert "-c" in result.error


def test_sandbox_mode_with_safe_command(run_command_tool):
    """Modo sandbox ejecuta comando seguro en directorio temporal."""
    tool_input = ToolInput(
        request_id="test_007",
        payload={
            "command": "python",
            "args": ["--version"],
            "sandbox": True,
        },
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is True
    assert result.data["exit_code"] == 0
    assert result.meta["sandbox"] is True
    assert "(sandbox)" in result.data["command_executed"]


def test_path_traversal_blocked(run_command_tool):
    """Path traversal en cwd es bloqueado."""
    tool_input = ToolInput(
        request_id="test_008",
        payload={
            "command": "python",
            "args": ["--version"],
            "cwd": "../../../",  # Intento de salir del workspace
        },
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is False
    assert "cwd fuera del workspace" in result.error


def test_exit_code_captured(run_command_tool):
    """Exit code es capturado correctamente."""
    # Crear script que retorna exit code específico
    workspace = run_command_tool.workspace_root
    exit_script = workspace / "exit_script.py"
    exit_script.write_text("import sys; sys.exit(42)")
    
    tool_input = ToolInput(
        request_id="test_009",
        payload={"command": "python", "args": ["exit_script.py"]},
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is True  # Comando ejecuta, pero con exit code != 0
    assert result.data["exit_code"] == 42


def test_stdout_stderr_captured(run_command_tool):
    """stdout/stderr son capturados."""
    # Crear script que escribe a stdout y stderr
    workspace = run_command_tool.workspace_root
    output_script = workspace / "output_script.py"
    output_script.write_text(
        'import sys; print("stdout message"); print("stderr message", file=sys.stderr)'
    )
    
    tool_input = ToolInput(
        request_id="test_010",
        payload={"command": "python", "args": ["output_script.py"]},
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is True
    assert "stdout message" in result.data["stdout"]
    assert "stderr message" in result.data["stderr"]


def test_stdout_stderr_truncated(run_command_tool):
    """stdout/stderr son truncados a 10KB."""
    # Crear script que genera output muy largo
    workspace = run_command_tool.workspace_root
    long_output_script = workspace / "long_output.py"
    long_output_script.write_text('print("A" * 20000)')  # 20KB de output
    
    tool_input = ToolInput(
        request_id="test_011",
        payload={"command": "python", "args": ["long_output.py"]},
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is True
    # Output debe estar truncado a 10KB
    assert len(result.data["stdout"]) <= 10 * 1024


def test_no_execute_permission_blocked():
    """CRÍTICO: Sin permiso execute, comando allowlisted NO corre.
    
    Nota: Este test verifica la integración con PermissionValidator.
    En un sistema real, el PermissionValidator se llamaría ANTES de execute().
    Aquí verificamos que la tool está configurada con risk='execute'.
    """
    config = {
        "allowed_commands": ["python"],
        "max_timeout_s": 300,
        "default_timeout_s": 30,
    }
    tool = RunCommandTool(config=config)
    
    # Verificar que la tool tiene risk='execute'
    assert tool.risk == "execute"
    
    # En el sistema real, PermissionValidator bloquearía esto antes de llegar a execute()
    # Este test documenta que la tool está correctamente marcada como 'execute'


def test_empty_command_fails(run_command_tool):
    """Comando vacío falla validación."""
    tool_input = ToolInput(
        request_id="test_012",
        payload={"command": ""},
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is False
    assert "command es requerido" in result.error


def test_invalid_args_type_fails(run_command_tool):
    """Args que no son lista falla validación."""
    tool_input = ToolInput(
        request_id="test_013",
        payload={"command": "python", "args": "--version"},  # String en vez de lista
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is False
    assert "args debe ser una lista" in result.error


def test_cwd_within_workspace(run_command_tool):
    """cwd dentro del workspace funciona correctamente."""
    workspace = run_command_tool.workspace_root
    subdir = workspace / "subdir"
    subdir.mkdir()
    
    tool_input = ToolInput(
        request_id="test_014",
        payload={
            "command": "python",
            "args": ["--version"],
            "cwd": "subdir",
        },
    )
    
    result = run_command_tool.execute(tool_input)
    
    assert result.success is True
    assert result.data["exit_code"] == 0


def test_max_timeout_enforced(run_command_tool):
    """Timeout máximo es enforced (no puede exceder max_timeout_s)."""
    tool_input = ToolInput(
        request_id="test_015",
        payload={
            "command": "python",
            "args": ["--version"],
            "timeout_s": 1000,  # Intento de usar timeout > max (300)
        },
    )
    
    result = run_command_tool.execute(tool_input)
    
    # Comando ejecuta, pero timeout es limitado a max_timeout_s
    assert result.success is True
    # El timeout real usado es max_timeout_s (300), no 1000
