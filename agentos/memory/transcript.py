"""
Transcript JSONL append-only por sesión.
Equivalente al sessionStorage.ts de Claude Code — fuente de verdad para restore/replay.

Cada línea es un JSON con:
  {"type": "user"|"agent"|"tool_call"|"tool_result"|"system",
   "content": "...",
   "session_id": "...",
   "uuid": "...",
   "ts": "iso8601"}
"""
import json
import uuid
import datetime
import os
from pathlib import Path
from typing import Optional, Iterator


class SessionTranscript:
    """
    Transcript JSONL por sesión. Append-only. Thread-safe para escrituras simples.
    """
    DEFAULT_DIR = "data/transcripts"

    def __init__(self, session_id: str, base_dir: str = DEFAULT_DIR):
        self.session_id = session_id
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.base_dir / f"{session_id}.jsonl"

    def append(self, msg_type: str, content: str, metadata: dict = None) -> str:
        """
        Agrega una línea al transcript. Retorna el uuid del mensaje.
        msg_type: "user" | "agent" | "tool_call" | "tool_result" | "system"
        """
        msg_uuid = str(uuid.uuid4())
        entry = {
            "type": msg_type,
            "content": content,
            "session_id": self.session_id,
            "uuid": msg_uuid,
            "ts": datetime.datetime.utcnow().isoformat(),
        }
        if metadata:
            entry.update(metadata)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return msg_uuid

    def read_all(self) -> list:
        """Lee todo el transcript. Retorna lista de dicts."""
        if not self._path.exists():
            return []
        entries = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    def iter_messages(self) -> Iterator[dict]:
        """Itera línea a línea sin cargar todo en memoria."""
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

    def get_summary(self) -> dict:
        """Metadata rápida sin leer el archivo completo."""
        if not self._path.exists():
            return {"session_id": self.session_id, "messages": 0, "exists": False}
        with open(self._path, "r", encoding="utf-8") as f:
            lines = sum(1 for line in f if line.strip())
        size = self._path.stat().st_size
        return {
            "session_id": self.session_id,
            "messages": lines,
            "size_bytes": size,
            "path": str(self._path),
            "exists": True,
        }

    @classmethod
    def list_sessions(cls, base_dir: str = DEFAULT_DIR) -> list:
        """Lista todas las sesiones con transcript."""
        base = Path(base_dir)
        if not base.exists():
            return []
        return [f.stem for f in base.glob("*.jsonl")]
