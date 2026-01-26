import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Extra fields (if present)
        for key in ("request_id", "session_id", "user_id", "agent", "tool"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "agentos", level: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if getattr(logger, "_agentos_configured", False):
        return logger

    logger.propagate = False
    logger.setLevel(getattr(logging, (level or "INFO").upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    logger._agentos_configured = True  # type: ignore[attr-defined]
    return logger
