from pathlib import Path
import pytest
from agentos.security.path_policy import PathPolicy
from agentos.agents.builder.patch_generator import PatchGenerator
from agentos.agents.builder.schemas import PlanSummary, PlanChange
from agentos.api.main import app
from fastapi.testclient import TestClient

# Mock ROOT for tests
TEST_ROOT = Path("/tmp/agentos_test_root")

class TestPathPolicy:
    
    @pytest.fixture
    def policy(self):
        # Usamos un path ficticio pero absoluto para el test
        return PathPolicy(TEST_ROOT)

    def test_path_traversal_blocked(self, policy):
        with pytest.raises(ValueError, match="traversal"):
            policy.validate_path("../../../etc/passwd")

    def test_absolute_path_linux_blocked(self, policy):
        # En Windows podría interpretarse diferente, pero PathPolicy chequea startswith('/')
        with pytest.raises(ValueError, match="absoluta"):
            policy.validate_path("/etc/passwd")

    def test_absolute_path_windows_blocked(self, policy):
        with pytest.raises(ValueError, match="absoluta"):
            policy.validate_path("C:\\Windows\\System32")

    def test_windows_drive_letter_blocked(self, policy):
        with pytest.raises(ValueError, match="Unidad Windows"):
            policy.validate_path("D:data")

    def test_protected_dir_blocked(self, policy):
        with pytest.raises(ValueError, match="Directorio protegido"):
            policy.validate_path(".cursor/rules/x.md")
            
    def test_protected_deployments_dir_blocked(self, policy):
        with pytest.raises(ValueError, match="Directorio protegido"):
            policy.validate_path("deployments/prod/x.yaml")

    def test_protected_file_blocked(self, policy):
        with pytest.raises(ValueError, match="Archivo protegido"):
            policy.validate_path("config/profiles.yaml")

    def test_root_prefix_attack_blocked(self, policy):
        # Ataque de prefijo para escapar del root
        with pytest.raises(ValueError, match="traversal"):
            policy.validate_path("../agentos_sibling")

    def test_false_positive_cursorfile_allowed(self, policy):
        # .cursorfile está permitido explícitamente
        res = policy.validate_path(".cursorfile")
        assert res.name == ".cursorfile"

    def test_valid_path_allowed(self, policy):
        res = policy.validate_path("agentos/agents/new_agent.py")
        expected = (TEST_ROOT / "agentos/agents/new_agent.py").resolve()
        assert res == expected


class TestPatchGenerator:
    
    def test_patch_generator_determinism(self):
        plan = PlanSummary(
            name="test", 
            description="desc",
            changes=[
                PlanChange(path="b.py", operation="create", content="b"),
                PlanChange(path="a.py", operation="create", content="a"),
            ]
        )
        
        diff1 = PatchGenerator.generate(plan)
        diff2 = PatchGenerator.generate(plan)
        
        assert diff1 == diff2
        assert diff1.find("a.py") < diff1.find("b.py")
        
    def test_patch_generator_format(self):
        plan = PlanSummary(
            name="test", description="desc",
            changes=[PlanChange(path="test.txt", operation="create", content="hello\nworld")]
        )
        diff = PatchGenerator.generate(plan)
        
        assert "diff --git a/test.txt b/test.txt" in diff
        assert "new file mode 100644" in diff
        assert "--- /dev/null" in diff
        assert "+++ b/test.txt" in diff
        assert "+hello" in diff


class TestApiContract:
    
    def test_scaffold_returns_full_structure(self):
        client = TestClient(app)
        response = client.post(
            "/builder/scaffold",
            json={"kind": "agent", "name": "api_contract_test", "description": "desc"},
            headers={"X-API-Key": "test-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "files" in data
        assert "plan" in data
        assert "unified_diff" in data
        assert "warnings" in data
        
        assert data["plan"]["name"] == "api_contract_test"
        assert len(data["files"]) > 0
        assert "diff --git" in data["unified_diff"]
        
    def test_scaffold_error_structure(self):
        # Provocar error con kind inválido
        client = TestClient(app)
        response = client.post(
            "/builder/scaffold",
            json={"kind": "INVALID_KIND", "name": "fail", "description": "desc"},
            headers={"X-API-Key": "test-key"}
        )
        
        # Debe retornar 200 OK con estructura de error, NO 500
        assert response.status_code == 200
        data = response.json()
        
        assert "plan" in data
        assert data["plan"]["name"] == "fail"
        assert len(data["plan"]["changes"]) == 0
        assert "error" in data["plan"]["metadata"]
        
        assert len(data["warnings"]) > 0
        assert "Error generating scaffold" in data["warnings"][0]
