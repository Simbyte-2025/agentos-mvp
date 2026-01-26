"""Integration tests for /builder/scaffold and /builder/apply endpoints."""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Guardar ROOT original antes de importar
import agentos.api.main as main_module

# Guardamos el ROOT original para restaurar después
_original_root = main_module.ROOT


@pytest.fixture
def test_project_root(tmp_path: Path):
    """Create a temporary project root for testing apply endpoint."""
    # Crear estructura mínima necesaria
    (tmp_path / "config").mkdir()
    (tmp_path / "agentos" / "agents" / "specialist").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    
    # Copiar archivos de config necesarios (sin ellos el app no inicia)
    config_src = Path(__file__).resolve().parents[2] / "config"
    for yaml_file in config_src.glob("*.yaml"):
        shutil.copy(yaml_file, tmp_path / "config" / yaml_file.name)
    
    return tmp_path


@pytest.fixture
def client_with_tmp_root(test_project_root: Path, monkeypatch):
    """Create a test client with ROOT pointing to temporary directory."""
    # Patch ROOT antes de crear el cliente
    monkeypatch.setattr(main_module, "ROOT", test_project_root)
    
    from agentos.api.main import app
    client = TestClient(app)
    
    yield client
    
    # Restaurar ROOT original
    monkeypatch.setattr(main_module, "ROOT", _original_root)


class TestBuilderScaffold:
    """Tests for /builder/scaffold endpoint."""
    
    def test_scaffold_agent_returns_files(self):
        """Scaffold kind=agent returns 2 files."""
        from agentos.api.main import app
        client = TestClient(app)
        
        response = client.post(
            "/builder/scaffold",
            json={
                "kind": "agent",
                "name": "echo",
                "description": "Agente que repite el input"
            },
            headers={"X-API-Key": "test-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 2
        
        paths = [f["path"] for f in data["files"]]
        assert any("echo_agent.py" in p for p in paths)
        assert any("test_echo_agent.py" in p for p in paths)
    
    def test_scaffold_tool_returns_files(self):
        """Scaffold kind=tool returns 2 files."""
        from agentos.api.main import app
        client = TestClient(app)
        
        response = client.post(
            "/builder/scaffold",
            json={
                "kind": "tool",
                "name": "json_parser",
                "description": "Parsea JSON",
                "risk": "read"
            },
            headers={"X-API-Key": "test-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 2
        
        paths = [f["path"] for f in data["files"]]
        assert any("json_parser.py" in p for p in paths)
        assert any("test_json_parser_tool.py" in p for p in paths)


class TestBuilderApply:
    """Tests for /builder/apply endpoint."""
    
    def test_apply_writes_files_to_filesystem(self, client_with_tmp_root, test_project_root):
        """Apply endpoint writes files to filesystem."""
        files = [
            {
                "path": "agentos/agents/specialist/test_apply_agent.py",
                "content": "# Test agent file\nclass TestApplyAgent:\n    pass\n"
            }
        ]
        
        response = client_with_tmp_root.post(
            "/builder/apply",
            json={"files": files, "overwrite": False},
            headers={"X-API-Key": "test-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["written"] == ["agentos/agents/specialist/test_apply_agent.py"]
        assert data["skipped"] == []
        assert data["errors"] == []
        
        # Verificar que el archivo existe
        created_file = test_project_root / "agentos/agents/specialist/test_apply_agent.py"
        assert created_file.exists()
        assert "TestApplyAgent" in created_file.read_text(encoding="utf-8")
    
    def test_apply_skips_existing_files_without_overwrite(self, client_with_tmp_root, test_project_root):
        """Apply skips existing files when overwrite=False."""
        # Crear archivo existente
        existing_path = test_project_root / "agentos/agents/specialist/existing_agent.py"
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_text("# Original content", encoding="utf-8")
        
        files = [
            {
                "path": "agentos/agents/specialist/existing_agent.py",
                "content": "# New content"
            }
        ]
        
        response = client_with_tmp_root.post(
            "/builder/apply",
            json={"files": files, "overwrite": False},
            headers={"X-API-Key": "test-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["skipped"] == ["agentos/agents/specialist/existing_agent.py"]
        
        # Contenido original sin cambios
        assert existing_path.read_text(encoding="utf-8") == "# Original content"
    
    def test_apply_overwrites_with_flag(self, client_with_tmp_root, test_project_root):
        """Apply overwrites files when overwrite=True."""
        existing_path = test_project_root / "agentos/agents/specialist/overwrite_me.py"
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_text("# Original", encoding="utf-8")
        
        files = [
            {
                "path": "agentos/agents/specialist/overwrite_me.py",
                "content": "# Overwritten"
            }
        ]
        
        response = client_with_tmp_root.post(
            "/builder/apply",
            json={"files": files, "overwrite": True},
            headers={"X-API-Key": "test-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["written"] == ["agentos/agents/specialist/overwrite_me.py"]
        
        # Contenido actualizado
        assert existing_path.read_text(encoding="utf-8") == "# Overwritten"
    
    def test_apply_blocks_absolute_paths(self, client_with_tmp_root):
        """Apply rejects absolute paths for security."""
        files = [
            {"path": "/etc/passwd", "content": "malicious"},
            {"path": "C:\\Windows\\system32\\test.txt", "content": "malicious"},
        ]
        
        response = client_with_tmp_root.post(
            "/builder/apply",
            json={"files": files, "overwrite": False},
            headers={"X-API-Key": "test-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) == 2
        assert all("absoluta" in e["error"] for e in data["errors"])
    
    def test_apply_blocks_path_traversal(self, client_with_tmp_root):
        """Apply rejects paths with '..' for security."""
        files = [
            {"path": "../../../etc/passwd", "content": "malicious"},
            {"path": "agentos/../../../secret.txt", "content": "malicious"},
        ]
        
        response = client_with_tmp_root.post(
            "/builder/apply",
            json={"files": files, "overwrite": False},
            headers={"X-API-Key": "test-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) == 2
        assert all("traversal" in e["error"] for e in data["errors"])


class TestBuilderE2EFlow:
    """End-to-end test: scaffold -> apply -> verify."""
    
    def test_scaffold_then_apply_creates_agent(self, client_with_tmp_root, test_project_root):
        """Full E2E: scaffold kind=agent, then apply, then verify files exist."""
        # Step 1: Scaffold
        scaffold_response = client_with_tmp_root.post(
            "/builder/scaffold",
            json={
                "kind": "agent",
                "name": "e2e_test",
                "description": "Agente de prueba E2E"
            },
            headers={"X-API-Key": "test-key"}
        )
        
        assert scaffold_response.status_code == 200
        scaffold_data = scaffold_response.json()
        assert len(scaffold_data["files"]) == 2
        
        # Step 2: Apply
        apply_response = client_with_tmp_root.post(
            "/builder/apply",
            json={"files": scaffold_data["files"], "overwrite": False},
            headers={"X-API-Key": "test-key"}
        )
        
        assert apply_response.status_code == 200
        apply_data = apply_response.json()
        assert len(apply_data["written"]) == 2
        assert apply_data["errors"] == []
        
        # Step 3: Verify files exist
        agent_file = test_project_root / "agentos/agents/specialist/e2e_test_agent.py"
        test_file = test_project_root / "tests/unit/test_e2e_test_agent.py"
        
        assert agent_file.exists(), f"Agent file not created: {agent_file}"
        assert test_file.exists(), f"Test file not created: {test_file}"
        
        # Verify content includes class name
        agent_content = agent_file.read_text(encoding="utf-8")
        assert "E2eTestAgent" in agent_content
        assert "BaseAgent" in agent_content
