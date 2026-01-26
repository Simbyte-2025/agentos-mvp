from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


class WorkingStateStore:
    """Estado de trabajo persistente con SQLite.

    - checkpoints(session_id, name, data_json, created_at)
    """

    def __init__(self, db_path: str | Path = "agentos_state.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    session_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, name)
                )
                """
            )

    def save_checkpoint(self, session_id: str, name: str, data: Dict[str, Any], created_at: str) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                "INSERT OR REPLACE INTO checkpoints(session_id, name, data_json, created_at) VALUES (?, ?, ?, ?)",
                (session_id, name, payload, created_at),
            )

    def load_checkpoint(self, session_id: str, name: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.execute(
                "SELECT data_json FROM checkpoints WHERE session_id = ? AND name = ?",
                (session_id, name),
            )
            row = cur.fetchone()
            if not row:
                return None
            return json.loads(row[0])
