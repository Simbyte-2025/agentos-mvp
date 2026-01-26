import os
import sys
from pathlib import Path

import pytest

from agentos.tools.base import ToolInput
from agentos.tools.exec.run_command import RunCommandTool


@pytest.fixture
def integration_workspace(tmp_path):
    """Crea workspace de integración con archivos de prueba."""
    workspace = tmp_path / "integration_workspace"
    workspace.mkdir()
    
    # Crear script Python simple
    script_file = workspace / "hello.py"
    script_file.write_text('print("Hello from integration test")')
    
    # Crear script que genera output
    output_script = workspace / "output.py"
    output_script.write_text('import sys; print("stdout"); print("stderr", file=sys.stderr)')
    
    # Crear script que retorna exit code
    exit_script = workspace / "exit_code.py"
    exit_script.write_text('import sys; sys.exit(0)')
    
    return workspace


@pytest.fixture
def integration_tool(integration_workspace):
    """Crea RunCommandTool para tests de integración."""
    config = {
        "allowed_commands": ["python", "pytest"],
        "max_timeout_s": 300,
        "default_timeout_s": 30,
    }
    return RunCommandTool(workspace_root=integration_workspace, config=config)


def test_run_python_script(integration_tool):
    """Ejecuta script Python simple."""
    tool_input = ToolInput(
        request_id="integration_002",
        payload={
            "command": "python",
            "args": ["hello.py"],
            "timeout_s": 30,
        },
    )
    
    result = integration_tool.execute(tool_input)
    
    assert result.success is True
    assert result.data["exit_code"] == 0
    assert "Hello from integration test" in result.data["stdout"]
    assert result.data["timed_out"] is False


def test_sandbox_mode_end_to_end(integration_tool):
    """Modo sandbox funciona end-to-end."""
    tool_input = ToolInput(
        request_id="integration_003",
        payload={
            "command": "python",
            "args": ["--version"],
            "sandbox": True,
            "timeout_s": 30,
        },
    )
    
    result = integration_tool.execute(tool_input)
    
    assert result.success is True
    assert result.data["exit_code"] == 0
    assert "Python" in result.data["stdout"]
    assert result.meta["sandbox"] is True
    assert "(sandbox)" in result.data["command_executed"]


def test_multiple_commands_sequentially(integration_tool):
    """Ejecuta múltiples comandos secuencialmente."""
    # Comando 1: python --version
    result1 = integration_tool.execute(
        ToolInput(
            request_id="integration_006_1",
            payload={"command": "python", "args": ["--version"]},
        )
    )
    assert result1.success is True
    
    # Comando 2: python script
    result2 = integration_tool.execute(
        ToolInput(
            request_id="integration_006_2",
            payload={"command": "python", "args": ["hello.py"]},
        )
    )
    assert result2.success is True


def test_real_world_scenario_python_execution(integration_tool):
    """Escenario real: ejecutar script Python con output."""
    tool_input = ToolInput(
        request_id="integration_007",
        payload={
            "command": "python",
            "args": ["output.py"],
            "timeout_s": 30,
        },
    )
    
    result = integration_tool.execute(tool_input)
    
    assert result.success is True
    assert result.data["exit_code"] == 0
    assert "stdout" in result.data["stdout"]
    assert "stderr" in result.data["stderr"]
    assert result.data["timed_out"] is False


def test_script_with_exit_code(integration_tool):
    """Ejecuta script que retorna exit code específico."""
    tool_input = ToolInput(
        request_id="integration_008",
        payload={
            "command": "python",
            "args": ["exit_code.py"],
            "timeout_s": 10,
        },
    )
    
    result = integration_tool.execute(tool_input)
    
    assert result.success is True
    assert result.data["exit_code"] == 0
    assert result.data["timed_out"] is False


def test_command_with_timeout(integration_tool):
    """Ejecuta comando con timeout configurado."""
    # Crear script que completa rápido
    workspace = integration_tool.workspace_root
    quick_script = workspace / "quick.py"
    quick_script.write_text('print("done")')
    
    tool_input = ToolInput(
        request_id="integration_009",
        payload={
            "command": "python",
            "args": ["quick.py"],
            "timeout_s": 5,
        },
    )
    
    result = integration_tool.execute(tool_input)
    
    assert result.success is True
    assert result.data["exit_code"] == 0
    assert "done" in result.data["stdout"]
    assert result.data["timed_out"] is False


def test_sandbox_with_python_script(integration_tool):
    """Ejecuta script Python en modo sandbox."""
    # Crear script simple
    workspace = integration_tool.workspace_root
    sandbox_script = workspace / "sandbox_test.py"
    sandbox_script.write_text('print("Running in sandbox")')
    
    # Nota: En sandbox, el script no estará disponible porque está en workspace
    # Pero podemos ejecutar --version que no requiere archivos
    tool_input = ToolInput(
        request_id="integration_010",
        payload={
            "command": "python",
            "args": ["--version"],
            "sandbox": True,
            "timeout_s": 10,
        },
    )
    
    result = integration_tool.execute(tool_input)
    
    assert result.success is True
    assert result.data["exit_code"] == 0
    assert result.meta["sandbox"] is True
