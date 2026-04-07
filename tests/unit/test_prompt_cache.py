"""Tests for agentos.llm.cache — Prompt caching."""

from agentos.llm.cache import CacheStats, PromptCache


class TestCacheStats:
    def test_initial(self):
        s = CacheStats()
        assert s.total == 0
        assert s.hit_rate == 0.0

    def test_hits_and_misses(self):
        s = CacheStats()
        s.record_hit()
        s.record_miss()
        s.record_hit()
        assert s.hits == 2
        assert s.misses == 1
        assert abs(s.hit_rate - 0.666) < 0.01

    def test_to_dict(self):
        s = CacheStats()
        s.record_hit()
        d = s.to_dict()
        assert d["hits"] == 1
        assert d["total"] == 1
        assert d["hit_rate"] == 1.0


class TestPromptCache:
    def test_put_and_get(self):
        cache = PromptCache()
        cache.put("hello world", "response1")
        assert cache.get("hello world") == "response1"
        assert cache.stats.hits == 1

    def test_miss(self):
        cache = PromptCache()
        assert cache.get("unknown") is None
        assert cache.stats.misses == 1

    def test_lru_eviction(self):
        cache = PromptCache(max_entries=2)
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")  # evicts "a"
        assert cache.get("a") is None
        assert cache.get("b") == "2"
        assert cache.get("c") == "3"

    def test_system_prompt_registration(self):
        cache = PromptCache()
        sp = "You are a helpful agent"
        assert cache.has_system_prompt(sp) is False
        cache.register_system_prompt(sp)
        assert cache.has_system_prompt(sp) is True

    def test_clear(self):
        cache = PromptCache()
        cache.put("a", "1")
        cache.clear()
        assert len(cache) == 0
        assert cache.get("a") is None

    def test_len(self):
        cache = PromptCache()
        assert len(cache) == 0
        cache.put("a", "1")
        assert len(cache) == 1
