from __future__ import annotations

import datetime
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List


class ShortTermMemory:
    """Memoria de corto plazo: últimos N mensajes por session_id.

    Mensajes se normalizan siempre al formato dict ``{role, content, ts}``.
    Se aceptan tanto strings legacy (con prefijo ``USER:`` / ``AGENT:``) como
    dicts ya estructurados.
    """

    def __init__(self, max_items: int = 50):
        self.max_items = max_items
        self._data: Dict[str, Deque[Any]] = defaultdict(lambda: deque(maxlen=max_items))

    def add(self, session_id: str, message: Any) -> None:
        """Agrega un mensaje al historial de la sesión.

        Acepta str o dict y normaliza siempre a ``{role, content, ts}``.
        """
        if isinstance(message, str):
            lower = message.lower()
            if lower.startswith("user:"):
                role = "user"
                content = message.split(":", 1)[1].strip()
            elif lower.startswith("agent"):
                role = "agent"
                content = message.split(":", 1)[1].strip() if ":" in message else message
            elif lower.startswith("system:"):
                role = "system"
                content = message.split(":", 1)[1].strip()
            else:
                role = "system"
                content = message
            message = {
                "role": role,
                "content": content,
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        elif isinstance(message, dict) and "ts" not in message:
            message = dict(message)
            message["ts"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        self._data[session_id].append(message)

    def get(self, session_id: str) -> List[Any]:
        return list(self._data.get(session_id, []))
