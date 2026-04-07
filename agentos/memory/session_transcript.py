"""JSONL-based session transcript persistence.

Inspired by jan-research src/services/SessionMemory/:
append-only JSONL files that survive process crashes and enable session
resumption.  Each line is a self-contained JSON message with role, content,
and timestamp.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


_DEFAULT_BASE_DIR = os.path.expanduser("~/.agentos/sessions")


class SessionTranscript:
    """Append-only JSONL transcript for a single session."""

    def __init__(self, session_id: str, base_dir: Optional[str] = None):
        self.session_id = session_id
        self._base_dir = Path(base_dir or os.getenv("AGENTOS_SESSIONS_DIR", _DEFAULT_BASE_DIR))
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._base_dir / f"{session_id}.jsonl"

    @property
    def path(self) -> Path:
        return self._path

    def append(self, role: str, content: str, meta: Optional[Dict[str, Any]] = None) -> None:
        """Append a message to the transcript immediately (crash-safe)."""
        entry: Dict[str, Any] = {
            "role": role,
            "content": content,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if meta:
            entry["meta"] = meta
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load(self) -> List[Dict[str, Any]]:
        """Load the full transcript from disk."""
        if not self._path.exists():
            return []
        messages: List[Dict[str, Any]] = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip corrupted lines — append-only is best-effort
                    pass
        return messages

    def message_count(self) -> int:
        if not self._path.exists():
            return 0
        count = 0
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    def delete(self) -> bool:
        """Remove transcript file. Returns True if deleted."""
        if self._path.exists():
            self._path.unlink()
            return True
        return False

    @classmethod
    def list_sessions(cls, base_dir: Optional[str] = None) -> List[str]:
        """List all session IDs with existing transcripts."""
        d = Path(base_dir or os.getenv("AGENTOS_SESSIONS_DIR", _DEFAULT_BASE_DIR))
        if not d.exists():
            return []
        return sorted(p.stem for p in d.glob("*.jsonl"))
