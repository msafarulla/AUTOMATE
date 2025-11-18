from playwright.sync_api import Page, Frame
from core.page_manager import PageManager
from core.screenshot import ScreenshotManager
from utils.hash_utils import HashUtils
from utils.wait_utils import WaitUtils
from utils.eval_utils import safe_page_evaluate, safe_locator_evaluate
import re
from core.logger import rf_log


class RFMenuManager:
    def __init__(
        self,
        page: Page,
        page_mgr: PageManager,
        screenshot_mgr: ScreenshotManager,
        verbose_logging: bool = False,
        auto_click_info_icon: bool = True,
        verify_tran_id_marker: bool = False,
    ):
        self.page = page
        self.page_mgr = page_mgr
        self.screenshot_mgr = screenshot_mgr
        self._maximized = False
        self._verify_tran_marker = verify_tran_id_marker
        self._tran_marker_verified = not verify_tran_id_marker
        self._last_home_hash = None
        self.verbose_logging = verbose_logging
        self._auto_click_info_icon = auto_click_info_icon
        self.screenshot_mgr.register_rf_capture_hooks(
            self._before_rf_snapshot,
            self._after_rf_snapshot,
        )

    def get_iframe(self) -> Frame:
        return self.page_mgr.get_rf_iframe()

    def ensure_maximized(self):
        """Ensure RF window is maximized from callers that know it should exist."""
        self._ensure_maximized()

    def reset_to_home(self):
        """Send Ctrl+B so RF navigation always starts from the home menu."""
        self._ensure_maximized()
        rf_iframe = self.get_iframe()
        body = rf_iframe.locator("body")
        body.wait_for(state="visible", timeout=2000)
        try:
            safe_locator_evaluate(body, "el => el.focus && el.focus()", description="RFMenuManager.reset_to_home focus")
        except Exception:
            pass

        prev_snapshot = HashUtils.get_frame_snapshot(rf_iframe)
        self.page.keyboard.press("Control+b")
        WaitUtils.wait_for_screen_change(
            self.get_iframe,
            prev_snapshot,
            warn_on_timeout=False,
        )
        if self._verify_tran_marker and not self._tran_marker_verified:
            if not self._home_menu_has_hash(rf_iframe):
                tran_prev_snapshot = HashUtils.get_frame_snapshot(rf_iframe)
                self.page.keyboard.press("Control+p")
                WaitUtils.wait_for_screen_change(rf_iframe, tran_prev_snapshot)
                if not self._home_menu_has_hash(rf_iframe):
                    self._log("⚠️ RF home menu never showed # marker after Control+P.")
                    self._tran_marker_verified = False
                else:
                    self._tran_marker_verified = True
            else:
                self._tran_marker_verified = True
        self.screenshot_mgr.capture_rf_window(self.page, "RF_HOME", "RF Home")

    def maximize_window(self):
        """Maximize RF Menu window"""
        try:
            success = safe_page_evaluate(
                self.page,
                """
            () => {
                const win = Ext.ComponentQuery.query('window[title~="RF"]')[0];
                if (!win) return false;
                win.setHeight(window.innerHeight * 0.9);
                win.center();
                win.updateLayout();
                return true;
            }
                """,
                description="RFMenuManager.maximize_window",
            )
        except Exception:
            success = False

        self._maximized = bool(success)
        return self._maximized

    def enter_choice(self, choice: str, ui_name: str) -> tuple[bool, str]:
        """Enter a choice in RF Menu and press Enter"""
        self._ensure_maximized()
        rf_iframe = self.get_iframe()
        choice_input = rf_iframe.locator("input[type='text']:visible").first
        choice_input.wait_for(timeout=1000)
        choice_input.fill(choice)

        self.screenshot_mgr.capture_rf_window(self.page, f"choice_{ui_name}",
                                              f"Selected {ui_name}")

        prev_snapshot = HashUtils.get_frame_snapshot(rf_iframe)
        choice_input.press("Enter")
        WaitUtils.wait_for_screen_change(self.get_iframe, prev_snapshot)

        return self.check_for_response(rf_iframe)

    def check_for_response(self, rf_iframe: Frame) -> tuple[bool, str] | tuple[bool, None]:
        """Check if an error or info screen appeared"""
        try:
            self.page.wait_for_timeout(500)
            visible_text = rf_iframe.locator("body").inner_text().strip()[:80]
            visible_text = re.sub(r"\s+", " ", visible_text)

            if re.search(r"(?i)info|warning", visible_text):
                message = f"{visible_text}"
                self._capture_response_screen(message)
                return False, message

            if re.search(r"(?i)error|invalid", visible_text):
                message = f"{visible_text}"
                self._capture_response_screen(message)
                return True, message

            return False, None
        except Exception:
            return False, None

    def accept_proceed(self, rf_iframe: Frame = None) -> bool:
        """Press Ctrl+A to accept/proceed"""
        if rf_iframe is None:
            rf_iframe = self.get_iframe()

        self.page.wait_for_timeout(500)
        if rf_iframe.locator("div.error").count() == 0:
            return False

        prev_snapshot = HashUtils.get_frame_snapshot(rf_iframe)
        self.page.keyboard.press("Control+a")
        WaitUtils.wait_for_screen_change(self.get_iframe, prev_snapshot)

        self.screenshot_mgr.capture_rf_window(self.page, "after_accept","Accepted/Proceeded")
        return True

    def _home_menu_has_hash(self, rf_iframe: Frame) -> bool:
        try:
            text = rf_iframe.locator("body").inner_text().strip()
        except Exception:
            return False
        hash_index = text.find('#')
        return hash_index != -1

    def _capture_response_screen(self, message: str):
        label = f"{self._slugify_for_filename(message)}"
        overlay_text = message[:120]
        self.screenshot_mgr.capture_rf_window(self.page, label, overlay_text)

    def _slugify_for_filename(self, text: str, max_len: int = 70) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
        if not slug:
            slug = "response"
        return slug[:max_len]

    def _ensure_maximized(self):
        if self._maximized:
            return
        try:
            if self.maximize_window():
                return
        except Exception:
            pass
        # If maximizing failed (window not available yet), try again later.
        self._maximized = False

    def click_info_icon(self) -> bool:
        """Click the blue info icon inside the RF iframe when available."""
        try:
            rf_iframe = self.get_iframe()
            icon = rf_iframe.locator("input[type='image'][src*='about.gif']:visible").first
            icon.wait_for(state="visible", timeout=1000)
        except Exception:
            return False

        prev_snapshot = None
        try:
            prev_snapshot = HashUtils.get_frame_snapshot(rf_iframe)
        except Exception:
            prev_snapshot = None

        try:
            icon.click()
            self._log("🛈 Clicked RF info icon inside iframe.")
        except Exception:
            return False

        if prev_snapshot is not None:
            try:
                WaitUtils.wait_for_screen_change(
                    self.get_iframe,
                    prev_snapshot,
                    warn_on_timeout=False,
                )
            except Exception:
                pass
        return True

    def _before_rf_snapshot(self):
        if self._auto_click_info_icon:
            self.click_info_icon()

    def _after_rf_snapshot(self):
        if self._auto_click_info_icon:
            self.click_info_icon()

    def _log(self, message: str):
        if self.verbose_logging:
            rf_log(message)
