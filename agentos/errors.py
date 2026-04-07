"""Structured error taxonomy for AgentOS.

Inspired by jan-research src/services/api/errors.ts:
typed error hierarchy enabling programmatic error handling,
retry decisions, and clear API error responses.
"""

from __future__ import annotations

from typing import Optional


class AgentOSError(Exception):
    """Base error for all AgentOS exceptions."""

    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, error_code: Optional[str] = None):
        super().__init__(message)
        if error_code:
            self.error_code = error_code


# --- Retryable errors ---

class RetryableError(AgentOSError):
    """Transient error that may succeed on retry."""

    error_code = "RETRYABLE_ERROR"

    def __init__(self, message: str, *, retry_after_seconds: Optional[float] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class RateLimitError(RetryableError):
    """API rate limit exceeded (HTTP 429)."""
    error_code = "RATE_LIMIT"


class ServiceOverloadedError(RetryableError):
    """Service temporarily overloaded (HTTP 529)."""
    error_code = "SERVICE_OVERLOADED"


class ServerError(RetryableError):
    """Upstream server error (HTTP 500/502/503/504)."""
    error_code = "SERVER_ERROR"


# --- Permanent errors ---

class PermanentError(AgentOSError):
    """Error that will not succeed on retry."""
    error_code = "PERMANENT_ERROR"


class ConfigurationError(PermanentError):
    """Missing or invalid configuration."""
    error_code = "CONFIGURATION_ERROR"


class AuthenticationError(PermanentError):
    """Invalid or missing credentials."""
    error_code = "AUTHENTICATION_ERROR"


class PermissionDeniedError(AgentOSError):
    """Agent lacks required permission for a tool/action."""
    error_code = "PERMISSION_DENIED"


class ContextOverflowError(AgentOSError):
    """Prompt + context exceeds model context window."""

    error_code = "CONTEXT_OVERFLOW"

    def __init__(self, message: str, *, token_count: Optional[int] = None, max_tokens: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.token_count = token_count
        self.max_tokens = max_tokens


class ToolExecutionError(AgentOSError):
    """Error during tool execution."""

    error_code = "TOOL_EXECUTION_ERROR"

    def __init__(self, message: str, *, tool_name: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.tool_name = tool_name


class ToolTimeoutError(ToolExecutionError):
    """Tool execution exceeded timeout."""
    error_code = "TOOL_TIMEOUT"


class OrchestrationError(AgentOSError):
    """Error in orchestration logic (planning, routing, replanning)."""
    error_code = "ORCHESTRATION_ERROR"


# --- Helpers ---

# HTTP status codes that indicate retryable errors
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504, 529})


def is_retryable_status(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES


def error_from_status(status_code: int, message: str, retry_after: Optional[float] = None) -> AgentOSError:
    """Create the appropriate error type from an HTTP status code."""
    if status_code == 429:
        return RateLimitError(message, retry_after_seconds=retry_after)
    if status_code == 529:
        return ServiceOverloadedError(message, retry_after_seconds=retry_after)
    if status_code in {500, 502, 503, 504}:
        return ServerError(message, retry_after_seconds=retry_after)
    if status_code == 401:
        return AuthenticationError(message)
    return PermanentError(message)
