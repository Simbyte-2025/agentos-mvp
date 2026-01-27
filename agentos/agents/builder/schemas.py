from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, field_validator


class PlanChange(BaseModel):
    """Representa un cambio individual en el plan."""
    path: str
    operation: Literal["create"]  # Restringido a create por ahora (MVP Lab)
    content: str
    
    @field_validator("operation")
    @classmethod
    def validate_operation(cls, v: str) -> str:
        if v != "create":
            raise ValueError("Solo operation='create' soportada en esta versión")
        return v


class PlanSummary(BaseModel):
    """Resumen estructurado del plan de scaffold."""
    name: str
    description: str
    changes: List[PlanChange]
    metadata: Dict[str, Any] = Field(default_factory=dict)
