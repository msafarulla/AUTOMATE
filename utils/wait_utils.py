# =============================================================================
# utils/wait_utils.py
# =============================================================================
"""Wait utilities for screen change detection."""

import time
from typing import Callable, Union
from playwright.sync_api import Frame

from utils.hash_utils import HashUtils
from utils.eval_utils import safe_page_evaluate, PageUnavailableError
from core.logger import app_log


FrameProvider = Callable[[], Frame]


class WaitUtils:
    """Wait utilities."""

    @staticmethod
    def wait_for_screen_change(
        frame_or_provider: Union[Frame, FrameProvider],
        prev_snapshot: str,
        timeout_ms: int = 25000,
        interval_ms: int = 200,
        warn_on_timeout: bool = True,
    ) -> bool:
        """
        Wait until frame content changes from previous snapshot.
        
        Args:
            frame_or_provider: Frame or callable that returns frame
            prev_snapshot: Previous snapshot to compare against
            timeout_ms: Maximum wait time
            interval_ms: Poll interval
            warn_on_timeout: Log warning if timeout reached
        
        Returns:
            True if content changed, False if timeout
        """
        def get_frame() -> Frame:
            if callable(frame_or_provider):
                f = frame_or_provider()
                if f is None:
                    raise RuntimeError("Frame provider returned None")
                return f
            return frame_or_provider

        try:
            frame = get_frame()
            page = frame.page
            start = safe_page_evaluate(page, "Date.now()", description="timer")

            while True:
                time.sleep(interval_ms / 1000)

                # Get current snapshot
                try:
                    frame = get_frame()
                    current = HashUtils.get_frame_snapshot(frame)
                except Exception as e:
                    if WaitUtils._is_navigation_error(e):
                        app_log("ℹ️ Frame navigated - treating as change")
                        return True
                    raise

                # Check if changed
                if current != (prev_snapshot or ""):
                    app_log("✅ Screen changed")
                    return True

                # Check timeout
                elapsed = safe_page_evaluate(page, "Date.now()", description="timer") - start
                if elapsed >= timeout_ms:
                    if warn_on_timeout:
                        app_log(f"⚠️ No change after {timeout_ms}ms")
                    return False

        except Exception as e:
            app_log(f"Error waiting for change: {e}")
            return False

    @staticmethod
    def wait_for_mask_clear(target, timeout_ms: int = 4000, selector: str = ".x-mask") -> bool:
        """Wait until no visible ExtJS mask is present (tolerant to detached pages/frames)."""
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
    def wait_brief(target, timeout_ms: int = 500, selector: str = ".x-mask"):
        """
        Wait for mask to clear, then wait out the remaining time via wait_for_function fallback.
        Keeps calls off bare wait_for_timeout to avoid blind sleeps.
        """
        start = time.time()
        try:
            WaitUtils.wait_for_mask_clear(target, timeout_ms=min(timeout_ms, 4000), selector=selector)
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

    @staticmethod
    def _is_navigation_error(exc: Exception) -> bool:
        """Check if error indicates frame navigation."""
        msg = str(exc).lower()
        markers = (
            "execution context was destroyed",
            "cannot find context",
            "frame was detached",
            "target closed",
        )
        return any(m in msg for m in markers) or isinstance(exc, PageUnavailableError)
