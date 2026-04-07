"""Tests for agentos.observability.metrics — MetricsCollector."""

from agentos.observability.metrics import MetricsCollector


class TestMetricsCollector:
    def test_initial_state(self):
        m = MetricsCollector()
        d = m.to_dict()
        assert d["requests"]["total"] == 0
        assert d["tokens"]["total_input"] == 0

    def test_record_request(self):
        m = MetricsCollector()
        m.record_request()
        m.record_request()
        assert m.to_dict()["requests"]["total"] == 2

    def test_record_success(self):
        m = MetricsCollector()
        m.record_success(duration_ms=100.0)
        d = m.to_dict()
        assert d["requests"]["success"] == 1
        assert d["duration_ms"]["api"] == 100.0

    def test_record_error(self):
        m = MetricsCollector()
        m.record_error("RATE_LIMIT")
        m.record_error("RATE_LIMIT")
        m.record_error("SERVER_ERROR")
        d = m.to_dict()
        assert d["requests"]["error"] == 3
        assert d["errors_by_code"]["RATE_LIMIT"] == 2
        assert d["errors_by_code"]["SERVER_ERROR"] == 1

    def test_record_llm_usage(self):
        m = MetricsCollector()
        m.record_llm_usage("claude-sonnet", input_tokens=100, output_tokens=50, duration_ms=200)
        m.record_llm_usage("claude-sonnet", input_tokens=200, output_tokens=100, duration_ms=300)
        d = m.to_dict()
        assert d["tokens"]["total_input"] == 300
        assert d["tokens"]["total_output"] == 150
        assert d["model_usage"]["claude-sonnet"]["calls"] == 2

    def test_record_tool_call(self):
        m = MetricsCollector()
        m.record_tool_call("read_file", duration_ms=10, success=True)
        m.record_tool_call("run_command", duration_ms=500, success=False)
        d = m.to_dict()
        assert d["tool_calls"]["read_file"] == 1
        assert d["tool_calls"]["run_command"] == 1
        assert d["tool_errors"]["run_command"] == 1
        assert "read_file" not in d["tool_errors"]

    def test_reset(self):
        m = MetricsCollector()
        m.record_request()
        m.record_llm_usage("model", 100, 50)
        m.reset()
        d = m.to_dict()
        assert d["requests"]["total"] == 0
        assert d["tokens"]["total_input"] == 0
        assert d["model_usage"] == {}
