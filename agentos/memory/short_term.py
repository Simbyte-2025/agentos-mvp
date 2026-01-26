from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List


class ShortTermMemory:
    """Memoria de corto plazo: últimos N mensajes por session_id."""

    def __init__(self, max_items: int = 10):
        self.max_items = max_items
        self._data: Dict[str, Deque[str]] = defaultdict(lambda: deque(maxlen=max_items))

    def add(self, session_id: str, message: str) -> None:
        self._data[session_id].append(message)

    def get(self, session_id: str) -> List[str]:
        return list(self._data.get(session_id, []))
