from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Any
from playwright.sync_api import Page
from utils.eval_utils import safe_page_evaluate, safe_locator_evaluate, PageUnavailableError
from core.logger import app_log


class ScreenshotManager:
    def __init__(self, output_dir: str = "screenshots", image_format: str = "png", image_quality: Optional[int] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.current_output_dir = self.output_dir
        self.current_scenario_dir = self.output_dir
        self.current_scenario_label: str | None = None
        self.current_stage_label: str | None = None
        self.sequence = 0
        fmt = (image_format or "png").lower()
        if fmt == "jpg":
            fmt = "jpeg"
        if fmt not in {"png", "jpeg"}:
            raise ValueError(f"Unsupported screenshot format: {image_format}")
        self.image_format = fmt
        self.image_quality = image_quality if (fmt == "jpeg" and image_quality is not None) else None
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
        filename = self._build_filename(label)
        overlay_added = False
        timestamp_added = False
        overlay_text_val = overlay_text or self._default_overlay_text()

        try:
            try:
                if overlay_text_val:
                    self._add_overlay(page, overlay_text_val)
                    overlay_added = True

                self._add_timestamp(page)
                timestamp_added = True
            except PageUnavailableError:
                app_log("⚠️ Page unavailable while decorating screenshot; continuing without overlays.")

            page.screenshot(**self._screenshot_kwargs(filename))
        except PageUnavailableError:
            app_log("⚠️ Unable to capture screenshot because the page/context closed.")
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

        app_log(f"📸 Screenshot saved: {filename}")
        return filename

    def capture_rf_window(self, page: Page, label: str, overlay_text: str = None):
        """Capture RF Menu window screenshot"""
        self.sequence += 1
        filename = self._build_filename(label)
        overlay_added = False
        timestamp_added = False
        overlay_text_val = overlay_text or self._default_overlay_text()

        try:
            self._run_rf_hook(self._rf_pre_capture_hook)
            rf_window = page.locator("div.x-window:has-text('RF Menu')")
            target = rf_window.first
            target.wait_for(timeout=2000)

            rect = self._get_element_rect(target)

            try:
                if overlay_text_val:
                    top = 2
                    self._add_overlay_to_target(target, overlay_text_val, top_offset=top)
                    overlay_added = True

                self._add_timestamp(page, rect)
                timestamp_added = True
            except PageUnavailableError:
                app_log("⚠️ RF window decorations skipped because the page/context closed.")

            target.screenshot(**self._screenshot_kwargs(filename))
        except PageUnavailableError:
            app_log("⚠️ Unable to capture RF window because the page/context closed.")
            return None
        except Exception as e:
            app_log(f"Failed to capture RF window: {e}")
            self._add_timestamp(page)
            timestamp_added = True
            page.screenshot(**self._screenshot_kwargs(filename))
        finally:
            if overlay_added:
                try:
                    self._remove_overlay_from_target(target)
                except PageUnavailableError:
                    pass
            if timestamp_added:
                try:
                    self._remove_timestamp(page)
                except PageUnavailableError:
                    pass
            self._run_rf_hook(self._rf_post_capture_hook)

        app_log(f"📸 RF Screenshot saved: {filename}")
        return filename

    def _build_filename(self, label: str) -> Path:
        suffix = ".jpg" if self.image_format == "jpeg" else ".png"
        return self.current_output_dir / f"{self.sequence:03d}_{label}{suffix}"

    def _screenshot_kwargs(self, filename: Path) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"path": str(filename), "type": self.image_format}
        if self.image_quality is not None:
            kwargs["quality"] = self.image_quality
        return kwargs

    def _run_rf_hook(self, hook: Optional[Callable[[], None]]):
        if not hook:
            return
        try:
            hook()
        except Exception as exc:
            app_log(f"⚠️ RF capture hook failed: {exc}")

    def set_scenario(self, scenario_name: str | None):
        """Switch the active screenshot folder to a scenario-specific subdirectory."""
        target_dir = self.output_dir
        if scenario_name:
            for segment in scenario_name.split("."):
                folder_name = self._sanitize_scenario_name(segment)
                target_dir = target_dir / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)
        self.current_scenario_dir = target_dir
        self.current_output_dir = target_dir
        self.current_scenario_label = scenario_name
        self.current_stage_label = None

    def set_stage(self, stage_name: str | None):
        """Create nested folder for the current stage within the active scenario."""
        if not self.current_scenario_dir:
            self.current_scenario_dir = self.output_dir
        target_dir = self.current_scenario_dir
        if stage_name:
            folder_name = self._sanitize_scenario_name(stage_name)
            target_dir = target_dir / folder_name
            target_dir.mkdir(parents=True, exist_ok=True)
        self.current_output_dir = target_dir
        self.current_stage_label = stage_name

    def _default_overlay_text(self) -> str | None:
        parts = []
        if self.current_scenario_label:
            parts.append(self.current_scenario_label)
        if self.current_stage_label:
            parts.append(self.current_stage_label)
        if not parts:
            return None
        return " / ".join(parts)
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
                    background: rgba(255,255,255,0.8);
                    color: rgba(10,10,10,0.95);
                    padding: 8px 20px;
                    font-size: 16px;
                    font-weight: 500;
                    font-family: 'Fira Code', monospace;
                    border-radius: 12px;
                    box-shadow: 0 5px 18px rgba(0,0,0,0.25);
                    backdrop-filter: blur(10px);
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

    def _add_overlay_to_target(self, target, text: str, top_offset: float = 40):
        target.evaluate(
            """
            (element, params) => {
                const style = window.getComputedStyle(element);
                if (!style.position || style.position === 'static') {
                    element.style.position = 'relative';
                }
                const existing = element.querySelector('#screenshot-overlay-text');
                if (existing) existing.remove();
                const overlay = document.createElement('div');
                overlay.id = 'screenshot-overlay-text';
                overlay.textContent = params.text;
                overlay.style.position = 'absolute';
                overlay.style.top = params.top + 'px';
                overlay.style.left = '50%';
                overlay.style.transform = 'translateX(-50%)';
                overlay.style.background = 'rgba(250,250,250,0.5)';
                    overlay.style.color = 'rgba(20,20,20,0.85)';
                    overlay.style.padding = '6px 20px';
                    overlay.style.fontSize = '15px';
                    overlay.style.fontWeight = '500';
                    overlay.style.fontFamily = 'Fira Code, monospace';
                    overlay.style.borderRadius = '16px';
                    overlay.style.boxShadow = '0 8px 20px rgba(0,0,0,0.35)';
                    overlay.style.backdropFilter = 'blur(12px)';
                overlay.style.zIndex = '99999999';
                overlay.style.pointerEvents = 'none';
                overlay.style.whiteSpace = 'nowrap';
                overlay.style.width = 'auto';
                overlay.style.maxWidth = '90%';
                element.appendChild(overlay);
            }
            """,
            {"text": text, "top": top_offset},
        )

    def _remove_overlay_from_target(self, target):
        target.evaluate(
            """
            () => {
                const overlay = document.getElementById('screenshot-overlay-text');
                if (overlay) overlay.remove();
            }
            """
        )

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

    def _sanitize_scenario_name(self, scenario_name: str) -> str:
        trimmed = scenario_name.strip()
        if not trimmed:
            return "unnamed"
        allowed = []
        for char in trimmed:
            if char.isalnum() or char in {"-", "_"}:
                allowed.append(char)
            else:
                allowed.append("_")
        sanitized = "".join(allowed).strip("_")
        return sanitized if sanitized else "unnamed"

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
