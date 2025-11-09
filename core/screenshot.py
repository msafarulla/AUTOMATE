import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from playwright.sync_api import Page, Frame
from utils.eval_utils import safe_page_evaluate, safe_locator_evaluate, PageUnavailableError


class ScreenshotManager:
    def __init__(self, output_dir: str = "screenshots"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.sequence = 0
        self._rf_pre_capture_hook: Optional[Callable[[], None]] = None
        self._rf_post_capture_hook: Optional[Callable[[], None]] = None

    def register_rf_capture_hooks(self,
                                  pre_hook: Optional[Callable[[], None]] = None,
                                  post_hook: Optional[Callable[[], None]] = None):
        """Allow RF flows to inject callbacks around every RF screenshot."""
        self._rf_pre_capture_hook = pre_hook
        self._rf_post_capture_hook = post_hook

    def capture(self, page: Page, label: str, overlay_text: str = None):
        """Capture full page screenshot"""
        self.sequence += 1
        filename = self.output_dir / f"{self.sequence:03d}_{label}.png"
        overlay_added = False
        timestamp_added = False

        try:
            try:
                if overlay_text:
                    self._add_overlay(page, overlay_text)
                    overlay_added = True

                self._add_timestamp(page)
                timestamp_added = True
            except PageUnavailableError:
                print("⚠️ Page unavailable while decorating screenshot; continuing without overlays.")

            page.screenshot(path=str(filename))
        except PageUnavailableError:
            print("⚠️ Unable to capture screenshot because the page/context closed.")
            return None
        finally:
            if overlay_added:
                try:
                    self._remove_overlay(page)
                except PageUnavailableError:
                    pass
            if timestamp_added:
                try:
                    self._remove_timestamp(page)
                except PageUnavailableError:
                    pass

        print(f"📸 Screenshot saved: {filename}")
        return filename

    def capture_rf_window(self, page: Page, label: str, overlay_text: str = None):
        """Capture RF Menu window screenshot"""
        self.sequence += 1
        filename = self.output_dir / f"{self.sequence:03d}_{label}.png"
        overlay_added = False
        timestamp_added = False

        try:
            self._run_rf_hook(self._rf_pre_capture_hook)
            rf_window = page.locator("div.x-window:has-text('RF Menu')")
            target = rf_window.first
            target.wait_for(timeout=2000)

            rect = self._get_element_rect(target)

            try:
                if overlay_text:
                    top = self._calculate_overlay_top(rect)
                    self._add_overlay(page, overlay_text, top_offset=top)
                    overlay_added = True

                self._add_timestamp(page, rect)
                timestamp_added = True
            except PageUnavailableError:
                print("⚠️ RF window decorations skipped because the page/context closed.")

            target.screenshot(path=str(filename))
        except PageUnavailableError:
            print("⚠️ Unable to capture RF window because the page/context closed.")
            return None
        except Exception as e:
            print(f"Failed to capture RF window: {e}")
            self._add_timestamp(page)
            timestamp_added = True
            page.screenshot(path=str(filename))
        finally:
            if overlay_added:
                try:
                    self._remove_overlay(page)
                except PageUnavailableError:
                    pass
            if timestamp_added:
                try:
                    self._remove_timestamp(page)
                except PageUnavailableError:
                    pass
            self._run_rf_hook(self._rf_post_capture_hook)

        print(f"📸 RF Screenshot saved: {filename}")
        return filename

    def _run_rf_hook(self, hook: Optional[Callable[[], None]]):
        if not hook:
            return
        try:
            hook()
        except Exception as exc:
            print(f"⚠️ RF capture hook failed: {exc}")

    def _add_overlay(self, page: Page, text: str, top_offset: float = 40):
        safe_page_evaluate(
            page,
            """
            (params) => {
                const existing = document.getElementById('screenshot-overlay-text');
                if (existing) existing.remove();

                const overlay = document.createElement('div');
                overlay.id = 'screenshot-overlay-text';
                overlay.textContent = params.text;
                overlay.style.cssText = `
                    position: fixed;
                    top: ${params.top}px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: linear-gradient(135deg, #3a7bd5, #00d2ff);
                    color: white;
                    padding: 12px 28px;
                    font-size: 22px;
                    font-weight: 500;
                    font-family: 'Fira Code', monospace;
                    border-radius: 10px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.25);
                    z-index: 99999999;
                    pointer-events: none;
                `;
                document.body.appendChild(overlay);
            }
            """,
            {"text": text, "top": float(top_offset)},
            description="ScreenshotManager._add_overlay",
        )
        page.wait_for_timeout(100)

    def _remove_overlay(self, page: Page):
        safe_page_evaluate(page, """
            () => {
                const overlay = document.getElementById('screenshot-overlay-text');
                if (overlay) overlay.remove();
            }
        """, description="ScreenshotManager._remove_overlay")

    def _calculate_overlay_top(self, rect: dict) -> float:
        if not rect:
            return 40.0
        return max(10.0, float(rect.get("top", 0.0)) + 20.0)

    def _get_element_rect(self, locator) -> dict:
        try:
            return safe_locator_evaluate(
                locator,
                """
                el => {
                    const r = el.getBoundingClientRect();
                    return { top: r.top, left: r.left, right: r.right, bottom: r.bottom };
                }
                """,
                description="ScreenshotManager._get_element_rect",
            )
        except Exception:
            return {}

    def _add_timestamp(self, page: Page, rect: dict | None = None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        params = {"text": timestamp}
        if rect:
            params["top"] = max(10.0, float(rect.get("bottom", 0.0)) - 18.0)
            params["left"] = max(10.0, float(rect.get("right", 0.0)) - 140.0)

        safe_page_evaluate(
            page,
            """
            (params) => {
                const existing = document.getElementById('screenshot-overlay-timestamp');
                if (existing) existing.remove();

                const el = document.createElement('div');
                el.id = 'screenshot-overlay-timestamp';
                el.textContent = params.text;
                el.style.cssText = `
                    position: fixed;
                    font-size: 11px;
                    color: rgba(0, 0, 0, 0.65);
                    font-family: 'Fira Code', monospace;
                    letter-spacing: 0.4px;
                    z-index: 99999999;
                    pointer-events: none;
                `;

                if (typeof params.top === 'number') {
                    el.style.top = `${params.top}px`;
                } else {
                    el.style.bottom = '16px';
                }

                if (typeof params.left === 'number') {
                    el.style.left = `${params.left}px`;
                    el.style.transform = 'none';
                } else {
                    el.style.right = '24px';
                }

                document.body.appendChild(el);
            }
            """,
            params,
            description="ScreenshotManager._add_timestamp",
        )

    def _remove_timestamp(self, page: Page):
        safe_page_evaluate(
            page,
            """
            () => {
                const el = document.getElementById('screenshot-overlay-timestamp');
                if (el) el.remove();
            }
            """,
            description="ScreenshotManager._remove_timestamp",
        )
