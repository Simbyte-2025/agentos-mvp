"""Tests for agentos.errors — Error taxonomy."""

from agentos.errors import (
    AgentOSError,
    AuthenticationError,
    ConfigurationError,
    ContextOverflowError,
    OrchestrationError,
    PermanentError,
    PermissionDeniedError,
    RateLimitError,
    RetryableError,
    ServerError,
    ServiceOverloadedError,
    ToolExecutionError,
    ToolTimeoutError,
    error_from_status,
    is_retryable_status,
)


class TestErrorHierarchy:
    def test_retryable_is_agentos_error(self):
        err = RetryableError("temp")
        assert isinstance(err, AgentOSError)

    def test_permanent_is_agentos_error(self):
        err = PermanentError("perm")
        assert isinstance(err, AgentOSError)

    def test_rate_limit_is_retryable(self):
        err = RateLimitError("429", retry_after_seconds=5.0)
        assert isinstance(err, RetryableError)
        assert err.retry_after_seconds == 5.0
        assert err.error_code == "RATE_LIMIT"

    def test_service_overloaded_is_retryable(self):
        err = ServiceOverloadedError("529")
        assert isinstance(err, RetryableError)
        assert err.error_code == "SERVICE_OVERLOADED"

    def test_server_error_is_retryable(self):
        err = ServerError("500")
        assert isinstance(err, RetryableError)

    def test_configuration_is_permanent(self):
        err = ConfigurationError("missing key")
        assert isinstance(err, PermanentError)

    def test_authentication_is_permanent(self):
        err = AuthenticationError("bad key")
        assert isinstance(err, PermanentError)

    def test_tool_timeout_is_tool_execution_error(self):
        err = ToolTimeoutError("timed out", tool_name="run_command")
        assert isinstance(err, ToolExecutionError)
        assert err.tool_name == "run_command"
        assert err.error_code == "TOOL_TIMEOUT"

    def test_context_overflow(self):
        err = ContextOverflowError("too big", token_count=50000, max_tokens=40000)
        assert err.token_count == 50000
        assert err.max_tokens == 40000

    def test_custom_error_code(self):
        err = AgentOSError("custom", error_code="MY_CODE")
        assert err.error_code == "MY_CODE"


class TestHelpers:
    def test_is_retryable_status(self):
        assert is_retryable_status(429) is True
        assert is_retryable_status(529) is True
        assert is_retryable_status(500) is True
        assert is_retryable_status(502) is True
        assert is_retryable_status(503) is True
        assert is_retryable_status(504) is True
        assert is_retryable_status(408) is True
        assert is_retryable_status(400) is False
        assert is_retryable_status(401) is False
        assert is_retryable_status(200) is False

    def test_error_from_status_429(self):
        err = error_from_status(429, "rate limited", retry_after=10)
        assert isinstance(err, RateLimitError)
        assert err.retry_after_seconds == 10

    def test_error_from_status_529(self):
        err = error_from_status(529, "overloaded")
        assert isinstance(err, ServiceOverloadedError)

    def test_error_from_status_500(self):
        err = error_from_status(500, "internal")
        assert isinstance(err, ServerError)

    def test_error_from_status_401(self):
        err = error_from_status(401, "unauthorized")
        assert isinstance(err, AuthenticationError)

    def test_error_from_status_unknown(self):
        err = error_from_status(400, "bad request")
        assert isinstance(err, PermanentError)
