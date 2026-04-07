"""Prompt caching support for Anthropic API.

Inspired by jan-research prompt caching with cache_control headers.
Tracks cache hit/miss rates for observability.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CacheStats:
    """Tracks prompt cache hit/miss rates."""
    hits: int = 0
    misses: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total if self.total > 0 else 0.0

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total": self.total,
            "hit_rate": round(self.hit_rate, 3),
        }


class PromptCache:
    """Simple LRU prompt cache for system prompts and repeated prefixes.

    Caches the hash of system prompts to detect when cache_control
    headers can be applied. Also provides a local response cache
    for identical prompts (useful in testing and deterministic flows).
    """

    def __init__(self, max_entries: int = 128):
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._max_entries = max_entries
        self.stats = CacheStats()

    @staticmethod
    def _hash_prompt(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

    def get(self, prompt: str) -> Optional[str]:
        """Get cached response for a prompt, if available."""
        key = self._hash_prompt(prompt)
        if key in self._cache:
            self._cache.move_to_end(key)
            self.stats.record_hit()
            return self._cache[key]
        self.stats.record_miss()
        return None

    def put(self, prompt: str, response: str) -> None:
        """Cache a response for a prompt."""
        key = self._hash_prompt(prompt)
        self._cache[key] = response
        self._cache.move_to_end(key)
        if len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)

    def has_system_prompt(self, system_prompt: str) -> bool:
        """Check if a system prompt hash is cached (for Anthropic cache_control)."""
        key = self._hash_prompt(system_prompt)
        return key in self._cache

    def register_system_prompt(self, system_prompt: str) -> None:
        """Register a system prompt hash for cache_control detection."""
        key = self._hash_prompt(system_prompt)
        if key not in self._cache:
            self._cache[key] = "__system_prompt__"
            if len(self._cache) > self._max_entries:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)
