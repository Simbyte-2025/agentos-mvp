"""Tool base classes with rich metadata.

Extended with patterns from jan-research src/tools/Tool.ts:
- input_schema (JSON Schema) for validation and documentation
- is_concurrent_safe flag for parallel execution
- tags for categorization and discovery
- ToolUseContext for execution context separate from AgentContext
"""

from __future__ import annotations

import concurrent.futures
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

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


class ToolTimeoutError(Exception):
    pass


@dataclass
class ToolUseContext:
    """Execution context passed to tools, separate from AgentContext.

    Keeps tool-specific concerns (abort, progress, model info) decoupled
    from agent-level concerns (memory, routing).
    """

    request_id: str = ""
    session_id: str = ""
    user_id: str = ""
    abort_event: Optional[threading.Event] = None
    on_progress: Optional[Callable[[str, float], None]] = None  # (message, pct)
    model_id: str = ""
    workspace_root: str = "."


class BaseTool(ABC):
    name: str
    description: str
    risk: str  # read | write | delete | execute
    tool_timeout: int = 30  # segundos, 0 = sin timeout

    # --- Rich metadata (new) ---
    input_schema: Dict[str, Any] = {}  # JSON Schema for payload validation
    is_concurrent_safe: bool = False   # Safe to run in parallel with other tools?
    tags: List[str] = []               # Categorization tags for discovery

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

    @property
    def is_destructive(self) -> bool:
        """Return True if this tool can delete or execute."""
        return self.risk in ("delete", "execute")

    @property
    def needs_permission(self) -> bool:
        """Return True if this tool requires explicit permission (non-read)."""
        return self.risk != "read"

    def dispatch(self, tool_input: ToolInput) -> ToolOutput:
        """Validate then execute. Preferred entry point over calling execute() directly."""
        validation = self.validate(tool_input)
        if not validation.valid:
            return ToolOutput(success=False, error=validation.error or "Validación fallida")
        return self.execute(tool_input)

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
