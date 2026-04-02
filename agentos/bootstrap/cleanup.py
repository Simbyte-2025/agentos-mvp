"""
Registry centralizado de cleanup handlers.
Garantiza que recursos críticos (SQLite, Chroma, file handles) se cierren
correctamente en shutdown normal y en SIGTERM.

Uso:
    from agentos.bootstrap.cleanup import register_cleanup
    register_cleanup(lambda: db.close())
"""
from __future__ import annotations

import atexit
import logging
import signal
from typing import Callable

logger = logging.getLogger(__name__)

_handlers: list = []
_shutdown_triggered: bool = False


def register_cleanup(fn: Callable, name: str = "") -> None:
    """Registra una función de cleanup. Se ejecutará al shutdown en orden LIFO."""
    _handlers.append((fn, name or getattr(fn, "__name__", "anonymous")))


def _run_cleanups(*args) -> None:
    global _shutdown_triggered
    if _shutdown_triggered:
        return
    _shutdown_triggered = True
    logger.info(f"[cleanup] Ejecutando {len(_handlers)} handlers de shutdown...")
    for fn, name in reversed(_handlers):
        try:
            fn()
            logger.debug(f"[cleanup] OK: {name}")
        except Exception as e:
            logger.error(f"[cleanup] ERROR en {name}: {e}")


# Registrar en atexit (shutdown normal) y SIGTERM
atexit.register(_run_cleanups)
try:
    signal.signal(signal.SIGTERM, _run_cleanups)
except (OSError, ValueError):
    # En algunos entornos (threads, Windows sin soporte completo) puede fallar
    pass
