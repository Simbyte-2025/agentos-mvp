"""Robust retry engine for LLM calls.

Inspired by jan-research src/services/api/withRetry.ts:
- Exponential backoff with jitter
- Retry-After header support
- Error classification (retryable vs permanent)
- Fallback model support
- Abort support via threading.Event
"""

from __future__ import annotations

import random
import time
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional, TypeVar

from agentos.errors import (
    RetryableError,
    PermanentError,
    error_from_status,
    is_retryable_status,
)
from agentos.observability.logging import get_logger

T = TypeVar("T")

logger = get_logger("agentos.llm.retry")


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""

    max_retries: int = 5
    base_delay: float = 0.5
    max_delay: float = 32.0
    jitter_factor: float = 0.25
    fallback_model: Optional[str] = None
    fallback_after_consecutive: int = 3

    def compute_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Compute delay for a given attempt, respecting retry-after if present."""
        if retry_after and retry_after > 0:
            return retry_after
        base = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        jitter = random.random() * self.jitter_factor * base
        return base + jitter


@dataclass
class RetryState:
    """Tracks retry state across calls for fallback decisions."""

    consecutive_failures: int = 0
    total_retries: int = 0
    fallback_triggered: bool = False


def retry_llm_call(
    fn: Callable[..., T],
    *args,
    policy: Optional[RetryPolicy] = None,
    abort_event: Optional[threading.Event] = None,
    retry_state: Optional[RetryState] = None,
    on_retry: Optional[Callable[[int, float, Exception], None]] = None,
    **kwargs,
) -> T:
    """Execute an LLM call with retry logic.

    Args:
        fn: The callable to retry.
        policy: Retry configuration. Uses defaults if None.
        abort_event: If set, abort between retries.
        retry_state: Shared state for tracking consecutive failures across calls.
        on_retry: Optional callback(attempt, delay, error) called before each retry sleep.

    Returns:
        The result of fn(*args, **kwargs).

    Raises:
        The last exception if all retries are exhausted or a permanent error occurs.
    """
    if policy is None:
        policy = RetryPolicy()
    if retry_state is None:
        retry_state = RetryState()

    last_error: Optional[Exception] = None

    for attempt in range(1, policy.max_retries + 2):
        # Check abort
        if abort_event and abort_event.is_set():
            raise InterruptedError("LLM call aborted")

        try:
            result = fn(*args, **kwargs)
            # Success — reset consecutive failures
            retry_state.consecutive_failures = 0
            return result

        except Exception as e:
            last_error = e

            # Extract HTTP status code if available
            status = _extract_status(e)

            # Non-retryable → raise immediately
            if status is not None and not is_retryable_status(status):
                retry_state.consecutive_failures += 1
                raise

            # If it's not a known retryable status and not our RetryableError, raise
            if status is None and not isinstance(e, RetryableError):
                retry_state.consecutive_failures += 1
                raise

            # Max retries exceeded
            if attempt > policy.max_retries:
                retry_state.consecutive_failures += 1
                raise

            retry_state.total_retries += 1
            retry_state.consecutive_failures += 1

            # Compute delay
            retry_after = _extract_retry_after(e)
            delay = policy.compute_delay(attempt, retry_after)

            logger.warning(
                "LLM call failed, retrying",
                extra={
                    "attempt": attempt,
                    "max_retries": policy.max_retries,
                    "delay_s": round(delay, 2),
                    "error": str(e)[:200],
                    "status": status,
                    "consecutive_failures": retry_state.consecutive_failures,
                },
            )

            if on_retry:
                on_retry(attempt, delay, e)

            # Check abort before sleeping
            if abort_event and abort_event.is_set():
                raise InterruptedError("LLM call aborted")

            time.sleep(delay)

    raise last_error  # type: ignore[misc]


def _extract_status(e: Exception) -> Optional[int]:
    """Extract HTTP status code from various exception types."""
    status = getattr(e, "status_code", None)
    if status is None:
        status = getattr(e, "status", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _extract_retry_after(e: Exception) -> Optional[float]:
    """Extract retry-after header value from exception."""
    try:
        val = e.response.headers.get("retry-after")  # type: ignore[union-attr]
        return float(val) if val else None
    except (AttributeError, TypeError, ValueError):
        return None
