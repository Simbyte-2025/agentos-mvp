"""
Sistema de composición modular de prompts.
Inspirado en systemPromptSections.ts de Claude Code.
"""
from typing import Callable, Optional


class PromptSection:
    """
    Sección componible de un system prompt.
    cached=True: el resultado se memoiza hasta invalidate().
    cached=False: se recalcula en cada resolve() (para contenido dinámico por llamada).
    """
    def __init__(self, name: str, compute: Callable[[], Optional[str]], cached: bool = True):
        self.name = name
        self._compute = compute
        self.cached = cached
        self._cache: Optional[str] = None

    def resolve(self) -> Optional[str]:
        if self.cached and self._cache is not None:
            return self._cache
        result = self._compute()
        if self.cached:
            self._cache = result
        return result

    def invalidate(self):
        self._cache = None

    def __repr__(self):
        return f"PromptSection(name={self.name!r}, cached={self.cached})"


def build_system_prompt(sections: list) -> str:
    """
    Construye un system prompt concatenando las secciones no-nulas.
    Retorna string listo para pasar a la API.
    """
    parts = []
    for s in sections:
        resolved = s.resolve() if isinstance(s, PromptSection) else s
        if resolved:
            parts.append(resolved.strip())
    return "\n\n".join(parts)


def build_messages_prompt(sections: list) -> list:
    """
    Retorna lista de strings para uso en messages API (system prompt cacheado por Anthropic).
    """
    return [s for s in (
        (sec.resolve() if isinstance(sec, PromptSection) else sec) for sec in sections
    ) if s]
