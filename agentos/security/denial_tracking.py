"""Permission denial tracking and escalation.

Inspired by jan-research src/utils/permissions/denialTracking.ts:
tracks consecutive and total denials per session to detect patterns
and trigger escalation (e.g., pause execution, ask user).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DenialRecord:
    """Tracks denial counts for a single session."""

    consecutive: int = 0
    total: int = 0
    history: List[Tuple[str, str]] = field(default_factory=list)  # (tool_name, action)

    def record_denial(self, tool_name: str, action: str) -> None:
        self.consecutive += 1
        self.total += 1
        self.history.append((tool_name, action))

    def record_success(self) -> None:
        self.consecutive = 0

    def reset(self) -> None:
        self.consecutive = 0
        self.total = 0
        self.history.clear()


class DenialTracker:
    """Tracks permission denials across sessions.

    Escalation thresholds:
    - consecutive_threshold: escalate after N consecutive denials (default: 3)
    - total_threshold: escalate after N total denials in session (default: 20)
    """

    def __init__(
        self,
        consecutive_threshold: int = 3,
        total_threshold: int = 20,
    ):
        self.consecutive_threshold = consecutive_threshold
        self.total_threshold = total_threshold
        self._records: Dict[str, DenialRecord] = defaultdict(DenialRecord)

    def record_denial(self, session_id: str, tool_name: str, action: str) -> None:
        self._records[session_id].record_denial(tool_name, action)

    def record_success(self, session_id: str) -> None:
        self._records[session_id].record_success()

    def should_escalate(self, session_id: str) -> bool:
        """Return True if denial pattern warrants escalation."""
        record = self._records.get(session_id)
        if record is None:
            return False
        return (
            record.consecutive >= self.consecutive_threshold
            or record.total >= self.total_threshold
        )

    def get_stats(self, session_id: str) -> Dict[str, int]:
        record = self._records.get(session_id)
        if record is None:
            return {"consecutive": 0, "total": 0}
        return {"consecutive": record.consecutive, "total": record.total}

    def get_history(self, session_id: str) -> List[Tuple[str, str]]:
        record = self._records.get(session_id)
        return list(record.history) if record else []

    def reset_session(self, session_id: str) -> None:
        if session_id in self._records:
            self._records[session_id].reset()

    def all_stats(self) -> Dict[str, Dict[str, int]]:
        """Return stats for all sessions (for /healthz)."""
        return {sid: self.get_stats(sid) for sid in self._records}
