"""Tests for agentos.llm.retry — Retry engine."""

import threading
import pytest
from unittest.mock import MagicMock

from agentos.errors import RetryableError, PermanentError, RateLimitError
from agentos.llm.retry import RetryPolicy, RetryState, retry_llm_call


class TestRetryPolicy:
    def test_default_values(self):
        p = RetryPolicy()
        assert p.max_retries == 5
        assert p.base_delay == 0.5
        assert p.max_delay == 32.0

    def test_compute_delay_with_retry_after(self):
        p = RetryPolicy()
        assert p.compute_delay(1, retry_after=10.0) == 10.0

    def test_compute_delay_exponential(self):
        p = RetryPolicy(jitter_factor=0)
        assert p.compute_delay(1) == 0.5
        assert p.compute_delay(2) == 1.0
        assert p.compute_delay(3) == 2.0
        assert p.compute_delay(10) == 32.0  # capped at max_delay


class TestRetryLLMCall:
    def test_success_no_retry(self):
        fn = MagicMock(return_value="ok")
        result = retry_llm_call(fn, policy=RetryPolicy(max_retries=3))
        assert result == "ok"
        assert fn.call_count == 1

    def test_retries_on_retryable_error(self):
        fn = MagicMock(side_effect=[
            RetryableError("fail1"),
            RetryableError("fail2"),
            "success",
        ])
        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        result = retry_llm_call(fn, policy=policy)
        assert result == "success"
        assert fn.call_count == 3

    def test_raises_permanent_error_immediately(self):
        fn = MagicMock(side_effect=PermanentError("bad request"))
        with pytest.raises(PermanentError):
            retry_llm_call(fn, policy=RetryPolicy(max_retries=3, base_delay=0.01))
        assert fn.call_count == 1

    def test_exhausts_retries(self):
        fn = MagicMock(side_effect=RetryableError("always fails"))
        policy = RetryPolicy(max_retries=2, base_delay=0.01)
        with pytest.raises(RetryableError):
            retry_llm_call(fn, policy=policy)
        assert fn.call_count == 3  # initial + 2 retries

    def test_abort_event_stops_retry(self):
        abort = threading.Event()
        abort.set()
        fn = MagicMock(side_effect=RetryableError("fail"))
        with pytest.raises(InterruptedError):
            retry_llm_call(fn, policy=RetryPolicy(max_retries=3), abort_event=abort)

    def test_retry_state_tracks_failures(self):
        state = RetryState()
        fn = MagicMock(side_effect=[
            RetryableError("fail"),
            "ok",
        ])
        retry_llm_call(fn, policy=RetryPolicy(max_retries=3, base_delay=0.01), retry_state=state)
        assert state.total_retries == 1
        assert state.consecutive_failures == 0  # reset on success

    def test_retries_on_status_code(self):
        err = Exception("server error")
        err.status_code = 500
        fn = MagicMock(side_effect=[err, "ok"])
        result = retry_llm_call(fn, policy=RetryPolicy(max_retries=3, base_delay=0.01))
        assert result == "ok"

    def test_no_retry_on_non_retryable_status(self):
        err = Exception("bad request")
        err.status_code = 400
        fn = MagicMock(side_effect=err)
        with pytest.raises(Exception, match="bad request"):
            retry_llm_call(fn, policy=RetryPolicy(max_retries=3, base_delay=0.01))
        assert fn.call_count == 1

    def test_on_retry_callback(self):
        calls = []
        fn = MagicMock(side_effect=[RetryableError("fail"), "ok"])
        retry_llm_call(
            fn,
            policy=RetryPolicy(max_retries=3, base_delay=0.01),
            on_retry=lambda attempt, delay, err: calls.append(attempt),
        )
        assert calls == [1]
