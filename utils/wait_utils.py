from playwright.sync_api import Page, Frame
from typing import Callable, Union
from utils.hash_utils import HashUtils
from utils.eval_utils import safe_page_evaluate, PageUnavailableError
from core.logger import app_log


FrameProvider = Callable[[], Frame]


class WaitUtils:

    @staticmethod
    def wait_for_screen_change(
            frame_or_provider: Union[Frame, FrameProvider],
            prev_hash: str,
            timeout_ms: int = 25000,
            check_interval_ms: int = 200,
            warn_on_timeout: bool = True,
    ) -> bool:
        """Wait for screen content to change by comparing hashes.

        Accepts either a Frame (legacy) or a callable that always returns the latest Frame so we
        can survive RF iframe recreations during navigation.
        """
        try:
            def _get_frame() -> Frame:
                if callable(frame_or_provider):
                    frame_obj = frame_or_provider()
                else:
                    frame_obj = frame_or_provider
                if frame_obj is None:
                    raise RuntimeError("Frame provider returned None while waiting for screen change.")
                return frame_obj

            frame = _get_frame()
            page = frame.page
            start_time = safe_page_evaluate(page, "Date.now()", description="WaitUtils.timer")

            while True:
                page.wait_for_timeout(check_interval_ms)
                try:
                    frame = _get_frame()
                    current_hash = HashUtils.get_frame_hash(frame)
                except Exception as exc:
                    if WaitUtils._is_frame_context_error(exc):
                        app_log("ℹ️ RF frame navigation detected while waiting; treating as screen change.")
                        return True
                    raise

                if current_hash != prev_hash:
                    app_log("✅ Screen content changed")
                    return True

                elapsed = safe_page_evaluate(page, "Date.now()", description="WaitUtils.timer") - start_time
                if elapsed >= timeout_ms:
                    if warn_on_timeout:
                        app_log(f"⚠️ Screen didn't change within {timeout_ms}ms")
                    return False
        except Exception as e:
            app_log(f"Error waiting for screen change: {e}")
            return False

    @staticmethod
    def _is_frame_context_error(exc: Exception) -> bool:
        """Return True if the Playwright error indicates the frame was recreated during navigation."""
        message = str(exc).lower()
        transient_markers = (
            "execution context was destroyed",
            "cannot find context with specified id",
            "frame was detached",
            "target closed",
        )
        if any(marker in message for marker in transient_markers):
            return True
        return isinstance(exc, PageUnavailableError)
