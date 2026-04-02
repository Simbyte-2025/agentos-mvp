"""
Schemas Pydantic para validación de configuración de AgentOS.
Inspirado en GlobalConfig / ProjectConfig de Claude Code.

Soporta Pydantic v1 y v2.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, field_validator, model_validator
    import pydantic
    PYDANTIC_V2 = int(pydantic.VERSION.split(".")[0]) >= 2
except ImportError:
    from pydantic import BaseModel, validator  # type: ignore
    PYDANTIC_V2 = False


class PermissionRule(BaseModel):
    """Una regla de permiso: qué tool y qué acciones están permitidas/prohibidas.

    Ejemplo en YAML:
        - tool: read_file
          actions: [read]
        - tool: "*"
          actions: [write, delete, execute]
    """
    tool: str
    actions: List[str]


class AgentProfileConfig(BaseModel):
    """Perfil de permisos para un agente (bloque bajo cada nombre en profiles.yaml)."""
    permissions: List[PermissionRule] = []
    forbidden: List[PermissionRule] = []


class AgentEntry(BaseModel):
    """Entrada de un agente en agents.yaml.

    Ejemplo:
        name: researcher_agent
        class_path: agentos.agents.specialist.researcher_agent.ResearcherAgent
        profile: researcher_agent
        description: "Investiga, recupera información y prepara hallazgos."
    """
    name: str
    class_path: str
    profile: str
    description: str = ""


class AgentsConfig(BaseModel):
    """Raíz de agents.yaml: lista de agentes registrados."""
    agents: List[AgentEntry]

    if PYDANTIC_V2:
        @field_validator("agents")
        @classmethod
        def validate_unique_names(cls, agents: List[AgentEntry]) -> List[AgentEntry]:
            names = [a.name for a in agents]
            if len(names) != len(set(names)):
                dupes = [n for n in names if names.count(n) > 1]
                raise ValueError(f"Nombres de agentes duplicados: {dupes}")
            return agents
    else:
        @classmethod  # type: ignore[misc]
        def validate_unique_names(cls, agents: List[AgentEntry]) -> List[AgentEntry]:
            names = [a.name for a in agents]
            if len(names) != len(set(names)):
                dupes = [n for n in names if names.count(n) > 1]
                raise ValueError(f"Nombres de agentes duplicados: {dupes}")
            return agents


class ProfilesConfig(BaseModel):
    """
    Raíz de profiles.yaml.

    profiles.yaml tiene estructura plana: {nombre_agente: {permissions, forbidden}}
    Se almacena como dict dinámico de AgentProfileConfig.
    """
    profiles: Dict[str, AgentProfileConfig] = {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfilesConfig":
        """Construye ProfilesConfig desde el dict plano de profiles.yaml."""
        parsed: Dict[str, AgentProfileConfig] = {}
        for agent_name, profile_data in (data or {}).items():
            parsed[agent_name] = AgentProfileConfig(**profile_data)
        return cls(profiles=parsed)

    def get_profile(self, name: str) -> Optional[AgentProfileConfig]:
        return self.profiles.get(name)
