# =============================================================================
# utils/wait_utils.py
# =============================================================================
"""Wait utilities for screen change detection."""

import time
from typing import Callable, Union
from playwright.sync_api import Frame

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
        Efficient screen-change detection using Playwright's wait_for_function.
        Runs comparison in browser context (no Python round trips).
        Falls back to a simple sleep if no frame is provided.
        """
        if frame_or_provider is None:
            try:
                time.sleep(max(0, timeout_ms) / 1000)
                return True
            except Exception as e:
                app_log(f"Error waiting for change: {e}")
                return False

        def get_frame() -> Frame:
            if callable(frame_or_provider):
                f = frame_or_provider()
                if f is None:
                    raise RuntimeError("Frame provider returned None")
                return f
            return frame_or_provider

        def snapshot(frame: Frame) -> str:
            try:
                text = frame.locator("body").inner_text(timeout=1000)
                # Use only the first few lines to detect movement; normalize whitespace.
                lines = text.splitlines()
                head = "\n".join(lines[:3])
                return " ".join(head.split())
            except Exception:
                return ""

        try:
            frame = get_frame()
            baseline = prev_snapshot if prev_snapshot is not None else snapshot(frame)

            # Use Playwright's efficient wait_for_function - runs in browser context
            frame.wait_for_function(
                """(baseline) => {
                    const lines = (document.body.innerText || '').split('\\n');
                    const current = lines.slice(0, 3).join(' ').replace(/\\s+/g, ' ').trim();
                    return current !== baseline;
                }""",
                arg=baseline,
                timeout=timeout_ms
            )
            app_log("✅ Screen changed")
            return True

        except Exception as e:
            if warn_on_timeout:
                app_log(f"⚠️ No change after {timeout_ms}ms")
                raise RuntimeError("⚠️ No change after {timeout_ms}ms")                
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
