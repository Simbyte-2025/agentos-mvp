from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def load_profiles(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"profiles.yaml no existe: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


@dataclass
class PermissionDecision:
    allowed: bool
    reason: str


class PermissionValidator:
    """Valida acceso a tools basado en perfiles.

    Regla simple:
    - Si está en forbidden: DENY
    - Si coincide con una permission (tool exacto o '*') y acción está incluida: ALLOW
    - Si no: DENY
    """

    def __init__(self, profiles: Dict[str, Any]):
        self.profiles = profiles

    def validate_tool_access(
        self,
        profile_name: str,
        tool_name: str,
        action: str,
    ) -> PermissionDecision:
        profile = self.profiles.get(profile_name)
        if not profile:
            return PermissionDecision(False, f"Perfil desconocido: {profile_name}")

        forbidden: List[Dict[str, Any]] = profile.get("forbidden", []) or []
        for rule in forbidden:
            if self._tool_matches(rule.get("tool", ""), tool_name) and action in (rule.get("actions") or []):
                return PermissionDecision(False, f"Acción prohibida por perfil: {profile_name}")

        permissions: List[Dict[str, Any]] = profile.get("permissions", []) or []
        for rule in permissions:
            if self._tool_matches(rule.get("tool", ""), tool_name) and action in (rule.get("actions") or []):
                return PermissionDecision(True, "Permitido")

        return PermissionDecision(False, "No permitido")

    @staticmethod
    def _tool_matches(pattern: str, tool_name: str) -> bool:
        if pattern == "*":
            return True
        return pattern == tool_name
