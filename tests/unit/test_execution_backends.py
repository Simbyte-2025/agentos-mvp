import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from agentos.tools.exec.backends.docker import DockerBackend
from agentos.tools.exec.backends.local import LocalBackend
from agentos.tools.exec.run_command import RunCommandTool


class TestExecutionBackendSelection:
    """Tests unitarios para la selección y fallback de backends en RunCommandTool."""

    def test_default_backend_is_local(self, monkeypatch):
        """Si no se configura nada, usa LocalBackend.
        
        Importante: asegurar que AGENTOS_EXEC_BACKEND no esté seteado o sea 'local'.
        """
        monkeypatch.delenv("AGENTOS_EXEC_BACKEND", raising=False)
        tool = RunCommandTool()
        assert isinstance(tool.backend, LocalBackend)

    def test_fallback_if_docker_unavailable(self, monkeypatch):
        """Fallback a LocalBackend si Docker no está disponible."""
        monkeypatch.setenv("AGENTOS_EXEC_BACKEND", "docker")
        
        # Simular que Docker no está disponible
        with patch.object(DockerBackend, "is_available", return_value=False):
            tool = RunCommandTool()
            assert isinstance(tool.backend, LocalBackend)

    def test_select_docker_if_available(self, monkeypatch):
        """Selecciona DockerBackend si está disponible y configurado."""
        monkeypatch.setenv("AGENTOS_EXEC_BACKEND", "docker")
        
        with patch.object(DockerBackend, "is_available", return_value=True):
            tool = RunCommandTool()
            assert isinstance(tool.backend, DockerBackend)

    def test_fallback_if_backend_invalid(self, monkeypatch):
        """Fallback a LocalBackend si el backend configurado no existe."""
        monkeypatch.setenv("AGENTOS_EXEC_BACKEND", "invalid_backend")
        tool = RunCommandTool()
        assert isinstance(tool.backend, LocalBackend)

    def test_fallback_for_unsupported_command(self, monkeypatch):
        """Fallback temporal a LocalBackend si el comando no es soportado (ej: dir).
        
        Valida comportamiento: DockerBackend configurado pero comando 'dir' fuerza uso de LocalBackend.
        """
        monkeypatch.setenv("AGENTOS_EXEC_BACKEND", "docker")
        
        # Simular Docker disponible para que se seleccione initially
        with patch.object(DockerBackend, "is_available", return_value=True):
            tool = RunCommandTool()
            # Confirmar que startamos con Docker
            assert isinstance(tool.backend, DockerBackend)
            
            # Mockear LocalBackend.execute para verificar que se llama
            with patch.object(LocalBackend, "execute") as mock_local_exec:
                # Retorno dummy para que la ejecución no falle
                mock_result = MagicMock()
                mock_result.exit_code = 0
                mock_result.stdout = "dir output"
                mock_result.stderr = ""
                mock_result.timed_out = False
                mock_result.duration_ms = 10
                mock_local_exec.return_value = mock_result
                
                # Mockear DockerBackend.execute para asegurar que NO se llama
                with patch.object(DockerBackend, "execute") as mock_docker_exec:
                    
                    # Ejecutar comando 'dir' (no soportado por DockerBackend)
                    tool_input = MagicMock()
                    tool_input.request_id = "test_req"
                    tool_input.payload = {"command": "dir", "args": []}
                    
                    tool.execute(tool_input)
                    
                    # Verificación robusta:
                    # 1. LocalBackend.execute FUE llamado (fallback ocurrió)
                    mock_local_exec.assert_called_once()
                    
                    # 2. DockerBackend.execute NO fue llamado
                    mock_docker_exec.assert_not_called()
                    
                    # 3. La instancia principal del backend sigue siendo Docker (fallback fue temporal)
                    assert isinstance(tool.backend, DockerBackend)
