"""
Generic automation orchestrator with retry logic and result summaries.
"""
from dataclasses import dataclass
from typing import Callable, Optional, Any

from config.settings import Settings
from core.connection_guard import ConnectionResetDetected
from core.logger import app_log


@dataclass
class OperationResult:
    """Result of an operation execution."""
    success: bool
    operation: str
    error: Optional[str] = None
    retry_count: int = 0


class AutomationOrchestrator:
    """Coordinates warehouse operations with retry logic and summary reporting."""

    def __init__(self, settings: Settings, max_retries: int = 3):
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
        retry_count = 0
        last_error: Optional[str] = None

        while retry_count < self.max_retries:
            try:
                prefix = "🔄 Retry" if retry_count else "▶️ Starting"
                app_log(f"{prefix} {operation_name} (attempt {retry_count + 1}/{self.max_retries})")

                success = operation_func(*args, **kwargs)
                if success:
                    result = OperationResult(True, operation_name, retry_count=retry_count)
                    app_log(f"✅ {operation_name} completed successfully")
                    self.results.append(result)
                    return result

                last_error = "Operation returned False"
                retry_count += 1
                if retry_count < self.max_retries:
                    app_log(f"⚠️ {operation_name} failed, retrying...")

            except ConnectionResetDetected:
                raise
            except Exception as exc:  # noqa: BLE001 - capture to retry
                last_error = str(exc)
                retry_count += 1
                app_log(f"❌ {operation_name} error: {exc}")
                if retry_count < self.max_retries:
                    app_log(f"🔄 Retrying {operation_name}...")

        result = OperationResult(False, operation_name, error=last_error, retry_count=retry_count)
        app_log(f"❌ {operation_name} failed after {retry_count} attempts")
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
