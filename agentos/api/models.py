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


class ScaffoldResponse(BaseModel):
    files: List[Dict[str, str]]
