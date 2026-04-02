from __future__ import annotations

import concurrent.futures
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


class ToolTimeoutError(Exception):
    pass


class BaseTool(ABC):
    name: str
    description: str
    risk: str  # read | write | delete | execute
    tool_timeout: int = 30  # segundos, 0 = sin timeout

    def __init__(self, name: str, description: str, risk: str = "read"):
        self.name = name
        self.description = description
        self.risk = risk

    @abstractmethod
    def execute(self, tool_input: ToolInput) -> ToolOutput:
        raise NotImplementedError


def execute_with_timeout(tool: BaseTool, tool_input: ToolInput, timeout_seconds: int = 30) -> ToolOutput:
    """Ejecuta tool.execute() con timeout.

    Lanza ToolTimeoutError si supera el límite.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(tool.execute, tool_input)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            raise ToolTimeoutError(
                f"Tool '{getattr(tool, 'name', str(tool))}' timed out after {timeout_seconds}s"
            )
