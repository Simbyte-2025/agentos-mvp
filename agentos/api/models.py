from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    task: str = Field(..., description="Descripción de la tarea")
    session_id: str = Field(..., description="Identificador de sesión")
    user_id: str = Field(..., description="Usuario")


class TaskResponse(BaseModel):
    agent: str
    success: bool
    output: str
    error: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ScaffoldRequest(BaseModel):
    kind: str = Field(..., description="agent|tool")
    name: str
    description: str
    risk: str = Field("read", description="read|write|delete|execute (solo si kind=tool)")


class PlanSummary(BaseModel):
    name: str
    description: str
    changes: List[Dict[str, str]] = Field(..., description="Lista de {path, operation}")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ScaffoldResponse(BaseModel):
    plan: PlanSummary
    files: List[Dict[str, str]] = Field(default_factory=list)
    unified_diff: str = Field("", description="Parche unificado compatible con git apply")
    warnings: List[str] = Field(default_factory=list)


class ApplyRequest(BaseModel):
    """Request para aplicar archivos generados por scaffold."""
    files: List[Dict[str, str]] = Field(..., description="Lista de {path, content}")
    overwrite: bool = Field(False, description="Si True, sobrescribe archivos existentes")


class ApplyResponse(BaseModel):
    """Respuesta de aplicar archivos."""
    written: List[str] = Field(default_factory=list, description="Archivos escritos exitosamente")
    skipped: List[str] = Field(default_factory=list, description="Archivos omitidos (ya existen)")
    errors: List[Dict[str, str]] = Field(default_factory=list, description="Errores {path, error}")
