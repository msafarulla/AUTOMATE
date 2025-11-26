"""
Generic automation orchestrator with retry logic and result summaries.
"""
from dataclasses import dataclass
from typing import Callable, Optional, Any

from config.settings import Settings
from core.connection_guard import ConnectionResetDetected
from core.logger import app_log
from utils.retry import retry, RetryExhausted


@dataclass
class OperationResult:
    """Result of an operation execution."""
    success: bool
    operation: str
    error: Optional[str] = None
    retry_count: int = 0


class AutomationOrchestrator:
    """Coordinates warehouse operations with retry logic and summary reporting."""

    def __init__(self, settings: Settings, max_retries: int = 1):
        self.settings = settings
        self.max_retries = max_retries
        self.results: list[OperationResult] = []

    def run_with_retry(
        self,
        operation_func: Callable[..., bool],
        operation_name: str,
        *args: Any,
        **kwargs: Any
    ) -> OperationResult:
        """Execute an operation with automatic retry on failure."""
        attempt_count = [0]  # Mutable to capture in callback

        def on_retry_callback(attempt: int, max_attempts: int, error: Exception):
            attempt_count[0] = attempt

        # Wrap function with retry decorator
        retried_func = retry(
            max_attempts=self.max_retries,
            catch=(Exception,),
            exclude=(ConnectionResetDetected,),
            log_prefix=operation_name,
            reraise=False,
            on_retry=on_retry_callback
        )(operation_func)

        try:
            success = retried_func(*args, **kwargs)
            final_attempt = attempt_count[0] if attempt_count[0] > 0 else 1

            if success:
                result = OperationResult(True, operation_name, retry_count=final_attempt - 1)
                self.results.append(result)
                return result
            else:
                result = OperationResult(
                    False,
                    operation_name,
                    error="Operation returned False",
                    retry_count=final_attempt
                )
                self.results.append(result)
                return result

        except ConnectionResetDetected:
            raise
        except RetryExhausted as exc:
            result = OperationResult(
                False,
                operation_name,
                error=str(exc.last_error),
                retry_count=exc.attempts
            )
            self.results.append(result)
            return result

    def print_summary(self):
        """Print summary of all operations executed in the current run."""
        app_log("\n" + "=" * 60)
        app_log("📊 OPERATION SUMMARY")
        app_log("=" * 60)

        total = len(self.results)
        successful = sum(1 for result in self.results if result.success)
        failed = total - successful

        app_log(f"Total operations: {total}")
        app_log(f"✅ Successful: {successful}")
        app_log(f"❌ Failed: {failed}")

        if failed:
            app_log("\nFailed operations:")
            for result in self.results:
                if not result.success:
                    app_log(f"  • {result.operation}: {result.error or 'Unknown error'}")

        app_log("=" * 60 + "\n")
