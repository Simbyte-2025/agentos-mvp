"""Tests for agentos.memory.consolidation_job — Memory consolidation."""

from agentos.memory.consolidation_job import ConsolidationJob, _extract_tags
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.long_term import LongTermMemory


class TestExtractTags:
    def test_code_tag(self):
        assert "code" in _extract_tags("La función calcula el resultado")

    def test_error_tag(self):
        assert "error" in _extract_tags("Error al procesar la solicitud")

    def test_http_tag(self):
        assert "http" in _extract_tags("Llamada HTTP a la API de datos")

    def test_general_fallback(self):
        assert _extract_tags("nada especial aquí") == ["general"]


class TestConsolidationJob:
    def _make_job(self, llm_fn=None, threshold=5):
        stm = ShortTermMemory(max_items=50)
        ltm = LongTermMemory()
        return ConsolidationJob(stm, ltm, llm_generate=llm_fn, consolidation_threshold=threshold), stm, ltm

    def test_should_consolidate(self):
        job, stm, _ = self._make_job(threshold=3)
        stm.add("s1", {"role": "user", "content": "a"})
        stm.add("s1", {"role": "agent", "content": "b"})
        assert job.should_consolidate("s1") is False
        stm.add("s1", {"role": "user", "content": "c"})
        assert job.should_consolidate("s1") is True

    def test_heuristic_consolidation(self):
        job, stm, ltm = self._make_job(threshold=1)
        # Only agent messages >50 chars get consolidated
        stm.add("s1", {"role": "agent", "content": "x" * 60 + " resultado importante"})
        stm.add("s1", {"role": "user", "content": "short"})
        added = job.run("s1")
        assert added == 1
        items = ltm.retrieve("resultado", top_k=5)
        assert len(items) >= 1

    def test_heuristic_skips_short_messages(self):
        job, stm, ltm = self._make_job(threshold=1)
        stm.add("s1", {"role": "agent", "content": "short"})
        added = job.run("s1")
        assert added == 0

    def test_llm_consolidation(self):
        def mock_llm(prompt: str) -> str:
            return "Hecho 1: Python es un lenguaje\nHecho 2: Se completó la tarea"

        job, stm, ltm = self._make_job(llm_fn=mock_llm, threshold=1)
        stm.add("s1", {"role": "user", "content": "explica python"})
        stm.add("s1", {"role": "agent", "content": "Python es un lenguaje de programación"})
        added = job.run("s1")
        assert added == 2
        items = ltm.retrieve("Python lenguaje", top_k=5)
        assert len(items) >= 1

    def test_llm_fallback_on_error(self):
        def failing_llm(prompt: str) -> str:
            raise RuntimeError("LLM down")

        job, stm, ltm = self._make_job(llm_fn=failing_llm, threshold=1)
        stm.add("s1", {"role": "agent", "content": "resultado " + "x" * 60})
        added = job.run("s1")
        # Falls back to heuristic
        assert added == 1

    def test_empty_session(self):
        job, stm, ltm = self._make_job(threshold=1)
        assert job.run("empty") == 0

    def test_tags_include_session_and_consolidated(self):
        job, stm, ltm = self._make_job(threshold=1)
        stm.add("s1", {"role": "agent", "content": "resultado del código " + "x" * 60})
        job.run("s1")
        items = ltm.retrieve("resultado", top_k=1)
        assert len(items) >= 1
        tags = items[0].tags
        assert "consolidated" in tags
        assert "session:s1" in tags
