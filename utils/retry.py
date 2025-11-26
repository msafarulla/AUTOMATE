"""
Unified retry utilities for automation operations.

Provides decorators and context managers for retry logic across the codebase.
"""
from functools import wraps
from typing import Callable, Optional, Any, TypeVar
from dataclasses import dataclass

from core.logger import app_log

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 2
    log_attempts: bool = True
    reraise_on_exhausted: bool = False
    catch_exceptions: tuple = (Exception,)
    exclude_exceptions: tuple = ()


class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted."""
    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Failed after {attempts} attempts: {last_error}")


def retry(
    max_attempts: int = 2,
    catch: tuple = (Exception,),
    exclude: tuple = (),
    log_prefix: str = "",
    reraise: bool = False,
    on_retry: Optional[Callable[[int, int, Exception], None]] = None
):
    """
    Decorator that retries a function on failure.

    Args:
        max_attempts: Maximum number of attempts (default: 2)
        catch: Tuple of exceptions to catch and retry (default: all Exception)
        exclude: Tuple of exceptions to immediately reraise (default: none)
        log_prefix: Prefix for log messages (default: function name)
        reraise: If True, reraise last exception when exhausted (default: False)
        on_retry: Optional callback(attempt, max_attempts, error) called on retry

    Returns:
        Decorated function that retries on failure

    Example:
        @retry(max_attempts=3, catch=(ValueError,), log_prefix="Database")
        def fetch_data():
            return db.query()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            prefix = log_prefix or func.__name__
            last_error: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    # Log attempt
                    if attempt == 1:
                        app_log(f"▶️ Starting {prefix}")
                    else:
                        app_log(f"🔄 Retry {prefix} (attempt {attempt}/{max_attempts})")

                    # Execute function
                    result = func(*args, **kwargs)

                    # Success
                    if result is not False:  # Allow None, but False indicates failure
                        if attempt > 1:
                            app_log(f"✅ {prefix} succeeded on attempt {attempt}")
                        return result

                    # Function returned False (soft failure)
                    last_error = ValueError(f"{prefix} returned False")
                    if attempt < max_attempts:
                        app_log(f"⚠️ {prefix} failed, retrying...")
                        if on_retry:
                            on_retry(attempt, max_attempts, last_error)

                except exclude as exc:
                    # Immediately reraise excluded exceptions
                    app_log(f"❌ {prefix} critical error: {exc}")
                    raise

                except catch as exc:
                    # Catch and potentially retry
                    last_error = exc
                    if attempt < max_attempts:
                        app_log(f"❌ {prefix} error: {exc}")
                        app_log(f"🔄 Retrying {prefix}...")
                        if on_retry:
                            on_retry(attempt, max_attempts, exc)

            # All attempts exhausted
            app_log(f"❌ {prefix} failed after {max_attempts} attempts")
            if reraise and last_error:
                raise RetryExhausted(max_attempts, last_error) from last_error
            return None  # type: ignore

        return wrapper
    return decorator


def retry_with_context(
    context: Any,
    max_attempts: int = 2,
    retry_field: str = "retry_count",
    max_field: str = "max_retries"
) -> bool:
    """
    Helper for context-based retry tracking (e.g., state machines).

    Args:
        context: Object with retry tracking fields
        max_attempts: Override max attempts (default: use context.max_retries)
        retry_field: Field name for retry counter
        max_field: Field name for max retries

    Returns:
        True if retries remain, False if exhausted

    Example:
        if retry_with_context(machine.context):
            # Still have retries
            return detect_and_recover()
        else:
            # Exhausted
            return ERROR_STATE
    """
    current = getattr(context, retry_field, 0)
    max_retries = max_attempts or getattr(context, max_field, 2)

    if current < max_retries:
        setattr(context, retry_field, current + 1)
        app_log(f"🔄 Retry {current + 1}/{max_retries}")
        return True

    app_log(f"❌ Retry limit exhausted ({max_retries} attempts)")
    return False


class RetryableOperation:
    """
    Context manager for operations with retry logic.

    Example:
        with RetryableOperation("Database Connection", max_attempts=3) as op:
            db.connect()
            op.success()  # Mark as successful
    """

    def __init__(self, name: str, max_attempts: int = 2):
        self.name = name
        self.max_attempts = max_attempts
        self.attempt = 0
        self.succeeded = False

    def __enter__(self):
        self.attempt += 1
        prefix = "🔄 Retry" if self.attempt > 1 else "▶️ Starting"
        app_log(f"{prefix} {self.name} (attempt {self.attempt}/{self.max_attempts})")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and self.succeeded:
            app_log(f"✅ {self.name} completed")
            return True

        if exc_type is not None:
            app_log(f"❌ {self.name} error: {exc_val}")

        if self.attempt < self.max_attempts:
            app_log(f"⚠️ {self.name} will retry...")

        return False  # Don't suppress exception

    def success(self):
        """Mark operation as successful."""
        self.succeeded = True
