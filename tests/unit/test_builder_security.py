import pytest
from pathlib import Path
from agentos.security.path_policy import PathPolicy, PathSecurityError
from agentos.agents.builder.patch_generator import PatchGenerator
from agentos.agents.builder.schemas import BuilderPlan, FileChange
from agentos.agents.builder.builder_agent import build_scaffold

@pytest.fixture
def root_dir(tmp_path):
    # Crear una estructura de repo simulada
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "profiles.yaml").write_text("profiles: {}")
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor" / "rules").mkdir()
    return tmp_path

@pytest.fixture
def policy(root_dir):
    return PathPolicy(root_dir=root_dir)

# --- TESTS DE SEGURIDAD DE RUTAS ---

def test_path_traversal_blocked(policy):
    with pytest.raises(PathSecurityError, match="Path Traversal"):
        policy.validate_path("../outside.py")

def test_absolute_path_blocked(policy):
    # Linux absolute
    with pytest.raises(PathSecurityError, match="Rutas absolutas"):
        policy.validate_path("/etc/passwd")

def test_windows_drive_blocked(policy):
    # Simular ruta con unidad de Windows (v2.3 usa Path.drive + regex)
    with pytest.raises(PathSecurityError, match="unidad de Windows"):
        policy.validate_path("C:\\temp\\x.py")

def test_protected_path_file_blocked(policy):
    with pytest.raises(PathSecurityError, match="Acceso a ruta protegida denegado"):
        policy.validate_path("config/profiles.yaml")

def test_protected_path_dir_blocked(policy):
    with pytest.raises(PathSecurityError, match="directorio protegido denegado"):
        policy.validate_path(".cursor/rules/RULE.md")

def test_prefix_root_attack_blocked(tmp_path):
    # Caso: root="/tmp/repo", ataque="/tmp/repo2/file"
    root = tmp_path / "repo"
    root.mkdir()
    other = tmp_path / "repo2"
    other.mkdir()
    (other / "secret.txt").write_text("secret")
    
    policy = PathPolicy(root_dir=root)
    
    # Intentar acceder a repo2 usando traversal relativo que resuelva fuera del root
    with pytest.raises(PathSecurityError, match="Path Traversal"):
        policy.validate_path("../repo2/secret.txt")

def test_cursorfile_not_blocked(policy):
    # ".cursorfile" NO debe bloquearse, solo ".cursor/"
    rel_path = policy.validate_path(".cursorfile")
    assert str(rel_path) == ".cursorfile"

# --- TESTS DE GENERACIÓN DE PARCHES ---

def test_deterministic_diff(root_dir):
    generator = PatchGenerator(root_dir=str(root_dir))
    
    plan = BuilderPlan(
        name="Test Plan",
        description="Test",
        changes=[
            FileChange(path="z.py", content="print('z')"),
            FileChange(path="a.py", content="print('a')"),
        ]
    )
    
    diff1 = generator.generate_unified_diff(plan)
    diff2 = generator.generate_unified_diff(plan)
    
    assert diff1 == diff2
    assert diff1.find("a.py") < diff1.find("z.py")

def test_git_compatible_format(root_dir):
    generator = PatchGenerator(root_dir=str(root_dir))
    plan = BuilderPlan(
        name="New File",
        description="Test",
        changes=[FileChange(path="new.py", content="hello")]
    )
    diff = generator.generate_unified_diff(plan)
    
    assert "diff --git a/new.py b/new.py" in diff
    assert "--- /dev/null" in diff
    assert "+++ b/new.py" in diff

# --- TESTS DE CONTRATO DE API (v2.3 Rebased) ---

def test_build_scaffold_contract(root_dir):
    res = build_scaffold(
        kind="agent",
        name="TestAgent",
        description="Testing API contract",
        root_dir=root_dir
    )
    
    # Verificar estructura del plan
    assert "plan" in res
    plan = res["plan"]
    assert plan["name"] == "Scaffold Agent: TestAgent"
    assert "changes" in plan
    assert "metadata" in plan
    assert len(plan["changes"]) > 0
    
    # Verificar presencia de campos obligatorios
    assert "files" in res
    assert "unified_diff" in res
    assert "warnings" in res
    
    # Aserciones estables
    assert "diff --git" in res["unified_diff"]
    assert "agentos/agents/" in res["unified_diff"]

def test_build_scaffold_error_contract(root_dir):
    # Forzar un error (kind inválido)
    res = build_scaffold(
        kind="invalid",
        name="Fail",
        description="Fail",
        root_dir=root_dir
    )
    
    # El contrato debe ser consistente incluso en error
    assert "error" in res
    assert "plan" in res
    assert "name" in res["plan"]
    assert "description" in res["plan"]
    assert "changes" in res["plan"]
    assert "metadata" in res["plan"]
    assert res["plan"]["changes"] == []
