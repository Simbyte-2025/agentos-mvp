"""Tests for agentos.security.denial_tracking."""

from agentos.security.denial_tracking import DenialRecord, DenialTracker


class TestDenialRecord:
    def test_record_denial(self):
        r = DenialRecord()
        r.record_denial("read_file", "read")
        assert r.consecutive == 1
        assert r.total == 1
        assert r.history == [("read_file", "read")]

    def test_record_success_resets_consecutive(self):
        r = DenialRecord()
        r.record_denial("t", "a")
        r.record_denial("t", "a")
        r.record_success()
        assert r.consecutive == 0
        assert r.total == 2

    def test_reset(self):
        r = DenialRecord()
        r.record_denial("t", "a")
        r.reset()
        assert r.consecutive == 0
        assert r.total == 0
        assert r.history == []


class TestDenialTracker:
    def test_no_escalation_initially(self):
        dt = DenialTracker()
        assert dt.should_escalate("s1") is False

    def test_escalate_after_consecutive(self):
        dt = DenialTracker(consecutive_threshold=3)
        for _ in range(3):
            dt.record_denial("s1", "tool", "execute")
        assert dt.should_escalate("s1") is True

    def test_escalate_after_total(self):
        dt = DenialTracker(total_threshold=5)
        for i in range(5):
            dt.record_denial("s1", "tool", "execute")
            dt.record_success("s1")  # reset consecutive
        assert dt.should_escalate("s1") is True

    def test_success_resets_consecutive(self):
        dt = DenialTracker(consecutive_threshold=3)
        dt.record_denial("s1", "t", "a")
        dt.record_denial("s1", "t", "a")
        dt.record_success("s1")
        dt.record_denial("s1", "t", "a")
        assert dt.should_escalate("s1") is False

    def test_get_stats(self):
        dt = DenialTracker()
        assert dt.get_stats("s1") == {"consecutive": 0, "total": 0}
        dt.record_denial("s1", "t", "a")
        assert dt.get_stats("s1") == {"consecutive": 1, "total": 1}

    def test_get_history(self):
        dt = DenialTracker()
        dt.record_denial("s1", "read_file", "read")
        dt.record_denial("s1", "run_command", "execute")
        assert dt.get_history("s1") == [("read_file", "read"), ("run_command", "execute")]

    def test_reset_session(self):
        dt = DenialTracker()
        dt.record_denial("s1", "t", "a")
        dt.reset_session("s1")
        assert dt.get_stats("s1") == {"consecutive": 0, "total": 0}

    def test_all_stats(self):
        dt = DenialTracker()
        dt.record_denial("s1", "t", "a")
        dt.record_denial("s2", "t", "b")
        stats = dt.all_stats()
        assert "s1" in stats
        assert "s2" in stats

    def test_isolated_sessions(self):
        dt = DenialTracker(consecutive_threshold=2)
        dt.record_denial("s1", "t", "a")
        dt.record_denial("s1", "t", "a")
        assert dt.should_escalate("s1") is True
        assert dt.should_escalate("s2") is False
