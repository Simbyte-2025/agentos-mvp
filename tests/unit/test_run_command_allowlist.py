import pytest

from agentos.security.run_command_allowlist import CommandAllowlist


def test_allowed_command_passes():
    """Comando en allowlist pasa validación."""
    allowlist = CommandAllowlist(allowed_commands=["python", "pytest"])
    decision = allowlist.validate("python", ["--version"])
    assert decision.allowed is True
    assert decision.reason == "Permitido"


def test_disallowed_command_fails():
    """Comando no en allowlist falla validación."""
    allowlist = CommandAllowlist(allowed_commands=["python", "pytest"])
    decision = allowlist.validate("del", ["file.txt"])
    assert decision.allowed is False
    assert "no está en allowlist" in decision.reason
    assert "python, pytest" in decision.reason


def test_shell_operators_blocked_in_command():
    """Operadores shell en comando son bloqueados."""
    allowlist = CommandAllowlist(allowed_commands=["python"])
    
    # Test cada operador peligroso (sin paréntesis - causan falsos positivos)
    # Nota: Verificamos en args ya que el comando debe estar en allowlist primero
    dangerous_operators = ["&&", "||", ";", "|", ">", "<", "$", "`"]
    for op in dangerous_operators:
        decision = allowlist.validate("python", [f"script{op}"])
        assert decision.allowed is False
        assert "Operador shell peligroso" in decision.reason


def test_shell_operators_blocked_in_args():
    """Operadores shell en args son bloqueados."""
    allowlist = CommandAllowlist(allowed_commands=["python"])
    
    # Test operadores en args
    decision = allowlist.validate("python", ["script.py", "&&", "del", "*"])
    assert decision.allowed is False
    assert "Operador shell peligroso" in decision.reason
    assert "&&" in decision.reason


def test_python_dangerous_args_blocked():
    """Python con args peligrosos (-c, -m, -) es bloqueado."""
    allowlist = CommandAllowlist(allowed_commands=["python"])
    
    # Test -c (sin usar semicolon que es operador shell)
    decision = allowlist.validate("python", ["-c", "1+1"])
    assert decision.allowed is False
    assert "Python arg peligroso bloqueado: '-c'" in decision.reason
    
    # Test -m
    decision = allowlist.validate("python", ["-m", "http.server"])
    assert decision.allowed is False
    assert "Python arg peligroso bloqueado: '-m'" in decision.reason
    
    # Test - (stdin)
    decision = allowlist.validate("python", ["-"])
    assert decision.allowed is False
    assert "Python arg peligroso bloqueado: '-'" in decision.reason


def test_python_safe_args_allowed():
    """Python con args seguros (--version, script.py) es permitido."""
    allowlist = CommandAllowlist(allowed_commands=["python"])
    
    # Test --version
    decision = allowlist.validate("python", ["--version"])
    assert decision.allowed is True
    
    # Test --help
    decision = allowlist.validate("python", ["--help"])
    assert decision.allowed is True
    
    # Test script.py
    decision = allowlist.validate("python", ["script.py"])
    assert decision.allowed is True
    
    # Test script.py con args
    decision = allowlist.validate("python", ["script.py", "--arg", "value"])
    assert decision.allowed is True


def test_allowlist_from_config():
    """Carga allowlist desde config."""
    config = {"allowed_commands": ["pytest", "dir"]}
    allowlist = CommandAllowlist(config=config)
    
    assert allowlist.validate("pytest", []).allowed is True
    assert allowlist.validate("dir", []).allowed is True
    assert allowlist.validate("python", []).allowed is False


def test_allowlist_from_env(monkeypatch):
    """Carga allowlist desde variable de entorno."""
    monkeypatch.setenv("AGENTOS_ALLOWED_COMMANDS", "python,pytest,dir,type")
    allowlist = CommandAllowlist()
    
    assert allowlist.validate("python", []).allowed is True
    assert allowlist.validate("pytest", []).allowed is True
    assert allowlist.validate("dir", []).allowed is True
    assert allowlist.validate("type", []).allowed is True
    assert allowlist.validate("del", []).allowed is False


def test_allowlist_default():
    """Allowlist default incluye python, pytest, dir, type."""
    allowlist = CommandAllowlist()
    
    assert allowlist.validate("python", []).allowed is True
    assert allowlist.validate("pytest", []).allowed is True
    assert allowlist.validate("dir", []).allowed is True
    assert allowlist.validate("type", []).allowed is True


def test_empty_args_allowed():
    """Comando sin args es permitido."""
    allowlist = CommandAllowlist(allowed_commands=["python"])
    decision = allowlist.validate("python", [])
    assert decision.allowed is True


def test_multiple_shell_operators():
    """Múltiples operadores shell son bloqueados."""
    allowlist = CommandAllowlist(allowed_commands=["python"])
    decision = allowlist.validate("python", ["script.py", "&&", "echo", "done", "|", "grep", "test"])
    assert decision.allowed is False
    assert "Operador shell peligroso" in decision.reason
