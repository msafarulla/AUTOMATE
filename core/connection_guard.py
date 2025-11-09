from __future__ import annotations

from typing import Callable, Optional, TypeVar

from playwright.sync_api import Frame, Page

from core.screenshot import ScreenshotManager


class ConnectionResetDetected(RuntimeError):
    """Raised when the browser shows the generic connection-reset error page."""


T = TypeVar("T")


class ConnectionResetGuard:
    """Watch the Playwright page for Chrome's connection-reset error screen."""

    ERROR_URL_PREFIXES = ("chrome-error://",)
    KEYWORDS = (
        "connection was reset",
        "err_connection_reset",
        "this site can't be reached",
        "this site can’t be reached",
    )

    def __init__(self, page: Page, screenshot_mgr: Optional[ScreenshotManager] = None):
        self.page = page
        self.screenshot_mgr = screenshot_mgr
        self._reason: Optional[str] = None
        page.on("framenavigated", self._handle_frame_navigation)
        page.on("domcontentloaded", self._handle_page_event)
        page.on("load", self._handle_page_event)

    def ensure_ok(self):
        """Raise immediately if the guard already detected the reset page."""
        if self._reason:
            raise ConnectionResetDetected(self._reason)

    def guard(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Run `func` and raise immediately if the reset page was seen before or after."""
        self.ensure_ok()
        try:
            result = func(*args, **kwargs)
        finally:
            self.ensure_ok()
        return result

    # --- internal helpers -------------------------------------------------

    def _handle_frame_navigation(self, frame: Frame):
        if frame == self.page.main_frame:
            self._check_frame(frame)

    def _handle_page_event(self, _page: Page):
        self._check_frame(self.page.main_frame)

    def _check_frame(self, frame: Frame):
        if self._reason:
            return

        url = (frame.url or "").lower()
        if any(url.startswith(prefix) for prefix in self.ERROR_URL_PREFIXES):
            self._trip(f"chrome error page loaded ({frame.url})")
            return

        try:
            body_text = frame.evaluate(
                "(document.body && document.body.innerText) || ''"
            )
        except Exception:
            return

        normalized = (body_text or "").lower()
        if any(keyword in normalized for keyword in self.KEYWORDS):
            self._trip("browser reported the connection was reset")

    def _trip(self, reason: str):
        if self._reason:
            return
        self._reason = reason
        print(f"❌ Connection reset detected: {reason}")
        if self.screenshot_mgr:
            try:
                self.screenshot_mgr.capture(self.page, "connection_reset", reason)
            except Exception:
                pass
