"""Permission validation with multi-mode support.

Modes (inspired by jan-research PermissionMode):
- strict: default-deny — only explicitly allowed actions pass (default)
- permissive: default-allow — only explicitly forbidden actions are blocked
- interactive: returns ``behavior='ask'`` for unmatched rules, letting the
  caller decide (useful for human-in-the-loop flows)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def load_profiles(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"profiles.yaml no existe: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


class PermissionMode(str, Enum):
    STRICT = "strict"
    PERMISSIVE = "permissive"
    INTERACTIVE = "interactive"


@dataclass
class PermissionDecision:
    allowed: bool
    reason: str
    behavior: str = "allow"  # "allow" | "deny" | "ask"


class PermissionValidator:
    """Valida acceso a tools basado en perfiles y modo de operación.

    Reglas de evaluación (independientes del modo):
    1. Si está en ``forbidden`` / ``always_deny``: DENY
    2. Si está en ``permissions`` / ``always_allow``: ALLOW
    3. Si está en ``always_ask``: ASK (solo en modo interactive)

    Comportamiento por modo cuando ninguna regla coincide:
    - strict: DENY (default-deny)
    - permissive: ALLOW (default-allow)
    - interactive: ASK (delegado al caller)
    """

    def __init__(self, profiles: Dict[str, Any], mode: PermissionMode | str = PermissionMode.STRICT):
        self.profiles = profiles
        self.mode = PermissionMode(mode) if isinstance(mode, str) else mode

    def set_mode(self, mode: PermissionMode | str) -> None:
        self.mode = PermissionMode(mode) if isinstance(mode, str) else mode

    def validate_tool_access(
        self,
        profile_name: str,
        tool_name: str,
        action: str,
    ) -> PermissionDecision:
        profile = self.profiles.get(profile_name)
        if not profile:
            return PermissionDecision(False, f"Perfil desconocido: {profile_name}", behavior="deny")

        # 1. Check forbidden / always_deny — always blocks
        for key in ("forbidden", "always_deny"):
            rules: List[Dict[str, Any]] = profile.get(key, []) or []
            for rule in rules:
                if self._tool_matches(rule.get("tool", ""), tool_name) and action in (rule.get("actions") or []):
                    return PermissionDecision(False, f"Acción prohibida por perfil: {profile_name}", behavior="deny")

        # 2. Check permissions / always_allow — always grants
        for key in ("permissions", "always_allow"):
            rules = profile.get(key, []) or []
            for rule in rules:
                if self._tool_matches(rule.get("tool", ""), tool_name) and action in (rule.get("actions") or []):
                    return PermissionDecision(True, "Permitido", behavior="allow")

        # 3. Check always_ask (explicit "ask" rules)
        ask_rules: List[Dict[str, Any]] = profile.get("always_ask", []) or []
        for rule in ask_rules:
            if self._tool_matches(rule.get("tool", ""), tool_name) and action in (rule.get("actions") or []):
                return PermissionDecision(False, "Requiere aprobación manual", behavior="ask")

        # 4. Default behavior depends on mode
        if self.mode == PermissionMode.PERMISSIVE:
            return PermissionDecision(True, "Permitido por modo permissive", behavior="allow")
        if self.mode == PermissionMode.INTERACTIVE:
            return PermissionDecision(False, "Sin regla explícita — requiere aprobación", behavior="ask")
        return PermissionDecision(False, "No permitido", behavior="deny")

    @staticmethod
    def _tool_matches(pattern: str, tool_name: str) -> bool:
        if pattern == "*":
            return True
        return pattern == tool_name
