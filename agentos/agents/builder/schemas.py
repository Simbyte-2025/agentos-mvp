from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any

@dataclass(frozen=True)
class FileChange:
    path: str
    content: str
    operation: str = "create"  # create | modify | delete

@dataclass(frozen=True)
class BuilderPlan:
    name: str
    description: str
    changes: List[FileChange]
    metadata: Dict[str, Any] = field(default_factory=dict)
