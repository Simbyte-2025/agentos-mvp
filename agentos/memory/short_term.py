from __future__ import annotations

import datetime
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List


class ShortTermMemory:
    """Memoria de corto plazo: últimos N mensajes por session_id."""

    def __init__(self, max_items: int = 10):
        self.max_items = max_items
        self._data: Dict[str, Deque[Any]] = defaultdict(lambda: deque(maxlen=max_items))

    def add(self, session_id: str, message) -> None:
        if isinstance(message, str):
            if message.lower().startswith("user:"):
                role, content = "user", message.split(":", 1)[1].strip()
            elif message.lower().startswith("agent:"):
                role, content = "agent", message.split(":", 1)[1].strip()
            else:
                role, content = "system", message
            message = {"role": role, "content": content, "ts": datetime.datetime.utcnow().isoformat()}
        elif isinstance(message, dict) and "ts" not in message:
            message = {**message, "ts": datetime.datetime.utcnow().isoformat()}
        self._data[session_id].append(message)

    def get(self, session_id: str) -> List[Any]:
        return list(self._data.get(session_id, []))
