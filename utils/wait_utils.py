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
        frame_or_provider: Union[Frame, FrameProvider, None] = None,
        prev_snapshot: str | None = None,
        timeout_ms: int = 25000,
        interval_ms: int = 200,
        warn_on_timeout: bool = True,
    ) -> bool:
        """
        Wait until frame content changes from previous snapshot.
        If no frame is provided, fall back to a simple pause.
        """
        if frame_or_provider is None:
            time.sleep(max(0, timeout_ms) / 1000)
            return True

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
            baseline = prev_snapshot or HashUtils.get_frame_snapshot(frame)

            while True:
                time.sleep(interval_ms / 1000)

                try:
                    frame = get_frame()
                    current = HashUtils.get_frame_snapshot(frame)
                except Exception as e:
                    if WaitUtils._is_navigation_error(e):
                        app_log("ℹ️ Frame navigated - treating as change")
                        return True
                    raise

                if current != (baseline or ""):
                    app_log("✅ Screen changed")
                    return True

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
