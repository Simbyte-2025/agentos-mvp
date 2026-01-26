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


class BaseTool(ABC):
    name: str
    description: str
    risk: str  # read | write | delete | execute

    def __init__(self, name: str, description: str, risk: str = "read"):
        self.name = name
        self.description = description
        self.risk = risk

    @abstractmethod
    def execute(self, tool_input: ToolInput) -> ToolOutput:
        raise NotImplementedError
