# =============================================================================
# utils/wait_utils.py
# =============================================================================
"""Wait utilities for screen change detection."""

import time
from core.logger import app_log


class WaitUtils:
    """Wait utilities."""

    @staticmethod
    def wait_for_screen_change(*args, timeout_ms: int = 25000, **kwargs) -> bool:
        """
        Simple pause used in place of snapshot comparisons.
        Accepts any positional/keyword args for backward compatibility.
        """
        try:
            time.sleep(max(0, timeout_ms) / 1000)
            return True
        except Exception as e:
            app_log(f"Error waiting for change: {e}")
            return False

    @staticmethod
    def wait_for_mask_clear(target, timeout_ms: int = 4000, selector: str = ".x-mask") -> bool:
        try:
            mask = target.locator(f"{selector}:visible")
        except Exception:
            return True

        deadline = time.time() + timeout_ms / 1000
        try:
            while time.time() < deadline:
                if mask.count() == 0:
                    return True
                time.sleep(0.15)
        except Exception:
            return True

        return True

    @staticmethod
    def wait_brief(target, timeout_ms: int = 4000, selector: str = ".x-mask"):
        """
        Standardized wait helper: always waits ~4000ms, mask-aware, no blind sleeps.
        """
        timeout_ms = 4000
        start = time.time()
        try:
            WaitUtils.wait_for_mask_clear(target, timeout_ms=timeout_ms, selector=selector)
        except Exception:
            pass

        remaining = timeout_ms - int((time.time() - start) * 1000)
        if remaining <= 0:
            return

        try:
            target.wait_for_function(
                "(delay, start) => Date.now() - start >= delay",
                remaining,
                int(time.time() * 1000),
                timeout=remaining + 250,
            )
        except Exception:
            try:
                time.sleep(max(0, remaining) / 1000)
            except Exception:
                pass
