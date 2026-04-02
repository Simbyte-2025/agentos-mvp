from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ValidationResult:
    """Result of a tool input validation check."""

    def __init__(self, valid: bool, error: Optional[str] = None, behavior: str = "deny"):
        self.valid = valid
        self.error = error
        self.behavior = behavior  # "deny" | "ask" | "allow"


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


class BaseTool(ABC):
    name: str
    description: str
    risk: str  # read | write | delete | execute

    def __init__(self, name: str, description: str, risk: str = "read"):
        self.name = name
        self.description = description
        self.risk = risk

    def validate(self, tool_input) -> ValidationResult:
        """Validate tool input before execution. Override to add custom checks."""
        return ValidationResult(valid=True)

    def is_read_only(self, tool_input=None) -> bool:
        """Return True if this tool call is read-only (no side effects)."""
        return getattr(self, "risk", "") == "read"

    @abstractmethod
    def execute(self, tool_input: ToolInput) -> ToolOutput:
        raise NotImplementedError
