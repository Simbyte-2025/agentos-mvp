"""
Validación de permisos con soporte de wildcards.
Equivalente al wildcard matching de Claude Code en permissionRules.
"""
import fnmatch
from typing import Optional


class ProfileValidator:
    """
    Valida si un agente puede ejecutar una tool con un input específico.

    Soporta wildcards en tool names:
      - "read_file" → exact match
      - "read_*"    → cualquier tool que empiece con read_
      - "*"         → todas las tools

    Soporta path_pattern para tools de filesystem:
      - path_pattern: "src/**" → solo archivos bajo src/
      - path_pattern: "*.py"   → solo archivos .py
    """

    def __init__(self, profiles: dict):
        self.profiles = profiles  # dict cargado desde profiles.yaml

    def can_execute(self, agent_name: str, tool_name: str, tool_input: dict = None) -> tuple[bool, str]:
        """
        Retorna (allowed: bool, reason: str).
        """
        profile = self.profiles.get(agent_name)
        if profile is None:
            return False, f"Perfil '{agent_name}' no encontrado"

        # Verificar forbidden primero (deny overrides allow)
        forbidden = profile.get("forbidden", [])
        for rule in forbidden:
            rule_tool = rule.get("tool", "")
            if fnmatch.fnmatch(tool_name, rule_tool):
                # Verificar path_pattern si existe
                if tool_input and "path_pattern" in rule:
                    path = tool_input.get("path", tool_input.get("file_path", ""))
                    if fnmatch.fnmatch(path, rule["path_pattern"]):
                        return False, f"Bloqueado por regla forbidden: {rule_tool} path={rule['path_pattern']}"
                elif "path_pattern" not in rule:
                    return False, f"Bloqueado por regla forbidden: {rule_tool}"

        # Verificar permissions
        permissions = profile.get("permissions", [])
        for rule in permissions:
            rule_tool = rule.get("tool", "")
            if fnmatch.fnmatch(tool_name, rule_tool):
                # Verificar path_pattern si existe
                if tool_input and "path_pattern" in rule:
                    path = tool_input.get("path", tool_input.get("file_path", ""))
                    if fnmatch.fnmatch(path, rule["path_pattern"]):
                        return True, f"Permitido por regla: {rule_tool} path={rule['path_pattern']}"
                elif "path_pattern" not in rule:
                    return True, f"Permitido por regla: {rule_tool}"

        return False, f"No hay regla de permiso para '{tool_name}' en perfil '{agent_name}'"

    def get_allowed_tools(self, agent_name: str) -> list:
        """Retorna lista de tool names permitidos para un agente (sin wildcards)."""
        profile = self.profiles.get(agent_name, {})
        return [r.get("tool", "") for r in profile.get("permissions", [])]
