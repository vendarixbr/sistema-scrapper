"""Retry handler using tenacity for robust async request handling."""

import logging
from typing import Any, Callable, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError,
)
from config import MAX_RETRIES

logger = logging.getLogger(__name__)

# Exception types that warrant a retry
_RETRYABLE = (TimeoutError, ConnectionError, OSError, IOError)


def with_retry(func: Callable) -> Callable:
    """Decorator: retries an async function with exponential backoff on transient errors."""
    return retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_random_exponential(min=2, max=30),
        retry=retry_if_exception_type(_RETRYABLE),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )(func)


async def safe_execute(func: Callable, *args: Any, **kwargs: Any) -> Optional[Any]:
    """Execute an async callable with retry; return None if all attempts fail."""
    decorated = retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_random_exponential(min=2, max=30),
        retry=retry_if_exception_type(_RETRYABLE),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )(func)
    try:
        return await decorated(*args, **kwargs)
    except (RetryError, Exception) as exc:
        logger.error("All retries exhausted for %s: %s", getattr(func, "__name__", func), exc)
        return None
