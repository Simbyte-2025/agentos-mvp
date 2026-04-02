from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ToolInput(BaseModel):
    """Input estándar para tools."""

    request_id: str = Field(..., description="Identificador de request")
    payload: Dict[str, Any] = Field(default_factory=dict)


class ToolOutput(BaseModel):
    """Output estándar para tools."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult:
    def __init__(self, valid: bool, error=None, behavior: str = "deny"):
        self.valid = valid
        self.error = error
        self.behavior = behavior


class BaseTool(ABC):
    name: str
    description: str
    risk: str  # read | write | delete | execute

    def __init__(self, name: str, description: str, risk: str = "read"):
        self.name = name
        self.description = description
        self.risk = risk

    def validate(self, tool_input) -> 'ValidationResult':
        return ValidationResult(valid=True)

    def is_read_only(self, tool_input=None) -> bool:
        return getattr(self, 'risk', '') == 'read'

    def dispatch(self, tool_input: ToolInput) -> ToolOutput:
        validation = self.validate(tool_input)
        if not validation.valid:
            return ToolOutput(success=False, error=validation.error or "Validación fallida")
        return self.execute(tool_input)

    @abstractmethod
    def execute(self, tool_input: ToolInput) -> ToolOutput:
        raise NotImplementedError
