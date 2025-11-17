from typing import Optional, Callable, Any
from playwright.sync_api import Page, Frame
from core.screenshot import ScreenshotManager
from utils.hash_utils import HashUtils
from utils.wait_utils import WaitUtils
from core.logger import rf_log


class RFPrimitives:

    INVALID_TEST_DATA_MSG = "Invalid test data"

    def __init__(
        self,
        page: Page,
        get_iframe_func: Callable[[], Frame],
        screenshot_mgr: ScreenshotManager,
        reset_to_home: Optional[Callable[[], None]] = None
    ):

        self.page = page
        self.get_iframe = get_iframe_func
        self.screenshot_mgr = screenshot_mgr
        self._reset_to_home = reset_to_home

    # ========================================================================
    # PRIMITIVE 1: Fill input field and submit
    # ========================================================================

    def fill_and_submit(
        self,
        selector: str,
        value: str,
        screenshot_label: str,
        screenshot_text: Optional[str] = None,
        wait_for_change: bool = True,
        check_errors: bool = True,
        timeout: int = 2000
    ) -> tuple[bool, Optional[str]]:

        rf_iframe = self.get_iframe()

        # Find and fill the input
        input_field = rf_iframe.locator(selector).first
        input_field.wait_for(state="visible", timeout=timeout)
        input_field.fill(value)

        # Take screenshot
        screenshot_text = screenshot_text or f"Entered {value}"
        self.screenshot_mgr.capture_rf_window(
            self.page,
            screenshot_label,
            screenshot_text
        )

        # Get hash before submit if we need to wait
        prev_snapshot = HashUtils.get_frame_snapshot(rf_iframe) if wait_for_change else None

        # Submit
        input_field.press("Enter")

        # Wait for screen change
        screen_changed = True
        if wait_for_change:
            screen_changed = WaitUtils.wait_for_screen_change(self.get_iframe, prev_snapshot)

        # If we were waiting for a change but it never happened, treat it as an error.
        if wait_for_change and not screen_changed:
            rf_log("⚠️ Submit did not trigger a screen change; treating as failure.")
            self.screenshot_mgr.capture_rf_window(
                self.page,
                "Error_submit_no_screen_change",
                "Submit failed to trigger a screen change"
            )
            return True, "Screen did not change after submit"

        # Check for errors
        if check_errors and screen_changed:
            has_error, msg = self._check_for_errors()
            if has_error:
                rf_log(f"❌ Operation failed with error: {msg[:150] if msg else 'Unknown error'}")
            return has_error, msg

        return False, None

    def fill_field(
        self,
        selector: str,
        value: str,
        screenshot_label: str,
        screenshot_text: Optional[str] = None,
        timeout: int = 2000
    ):

        rf_iframe = self.get_iframe()

        input_field = rf_iframe.locator(selector).first
        input_field.wait_for(state="visible", timeout=timeout)
        input_field.fill(value)

        screenshot_text = screenshot_text or f"Filled {value}"
        self.screenshot_mgr.capture_rf_window(
            self.page,
            screenshot_label,
            screenshot_text
        )

        return input_field

    def submit_current_input(
        self,
        screenshot_label: str,
        screenshot_text: Optional[str] = None,
        wait_for_change: bool = True,
        check_errors: bool = True,
        timeout: int = 2000,
        selector: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:

        rf_iframe = self.get_iframe()
        if selector:
            target_input = rf_iframe.locator(selector).first
        else:
            target_input = rf_iframe.locator(":focus")
        target_input.wait_for(state="visible", timeout=timeout)

        screenshot_text = screenshot_text or "Submitted focused input"
        self.screenshot_mgr.capture_rf_window(
            self.page,
            screenshot_label,
            screenshot_text
        )

        prev_snapshot = HashUtils.get_frame_snapshot(rf_iframe) if wait_for_change else None
        target_input.press("Enter")

        if wait_for_change:
            WaitUtils.wait_for_screen_change(self.get_iframe, prev_snapshot)

        if check_errors:
            has_error, msg = self._check_for_errors()
            if has_error:
                rf_log(f"❌ Operation failed with error: {msg[:150] if msg else 'Unknown error'}")
            return has_error, msg

        return False, None

    # ========================================================================
    # PRIMITIVE 2: Read a field value
    # ========================================================================

    def read_field(
        self,
        selector: str,
        timeout: int = 5000,
        transform: Optional[Callable[[str], str]] = None
    ) -> str:

        rf_iframe = self.get_iframe()
        locator = rf_iframe.locator(selector)
        locator.wait_for(state="visible", timeout=timeout)
        value = locator.inner_text().strip()

        if transform:
            value = transform(value)

        return value

    # ========================================================================
    # PRIMITIVE 3: Navigate menu by number
    # ========================================================================

    def select_menu_option(
        self,
        choice: str,
        label: str,
        timeout: int = 1000
    ) -> tuple[bool, Optional[str]]:
        return self.fill_and_submit(
            selector="input[type='text']:visible",
            value=choice,
            screenshot_label=f"choice_{label}",
            screenshot_text=f"Selected {label}",
            timeout=timeout
        )

    # ========================================================================
    # PRIMITIVE 4: Keyboard shortcuts
    # ========================================================================

    def press_key(
        self,
        key: str,
        screenshot_label: str,
        screenshot_text: Optional[str] = None,
        wait_for_change: bool = True
    ):

        rf_iframe = self.get_iframe()

        prev_snapshot = HashUtils.get_frame_snapshot(rf_iframe) if wait_for_change else None

        self.page.keyboard.press(key)

        if wait_for_change:
            WaitUtils.wait_for_screen_change(self.get_iframe, prev_snapshot)

        screenshot_text = screenshot_text or f"Pressed {key}"
        self.screenshot_mgr.capture_rf_window(self.page, screenshot_label, screenshot_text)

    # ========================================================================
    # PRIMITIVE 5: Common keyboard shortcuts (semantic wrappers)
    # ========================================================================

    def go_home(self):
        """Navigate to RF home screen (Ctrl+B with tran id display)."""
        if self._reset_to_home:
            self._reset_to_home()
            return
        self.press_key("Control+b", "RF_HOME", "RF Home")

    def ensure_tran_id_marker(self):
        """Ensure the tran id marker is visible on the RF home screen."""
        # Best-effort single Ctrl+P without hash validation
        self.press_key("Control+p", "rf_tran_marker", "Show tran id", wait_for_change=False)

    def accept_message(self):
        """Accept/proceed from info or error screen (Ctrl+A)."""
        self.press_key("Control+a", "accepted_message", "Accepted/Proceeded")

    def handle_error_and_continue(self) -> bool:

        has_error, msg = self._check_for_errors()
        if msg:  # If there's any message (error or info)
            rf_log(f"{'❌ Error' if has_error else 'ℹ️ Info'}: {msg[:100]}")
            self.accept_message()
            return has_error
        return False

    # ========================================================================
    # HELPER: Error checking
    # ========================================================================

    def _check_for_errors(self) -> tuple[bool, Optional[str]]:
        try:
            rf_iframe = self.get_iframe()
            self.page.wait_for_timeout(500)

            # Get full text and normalize whitespace/newlines
            visible_text = rf_iframe.locator("body").inner_text().strip()
            # Replace newlines and multiple spaces with single space
            import re
            visible_text_normalized = re.sub(r'\s+', ' ', visible_text)
            visible_text_lower = visible_text_normalized.lower()

            # Check for errors (case insensitive)
            if "error" in visible_text_lower or "invalid" in visible_text_lower:
                # Create clean label for filename (remove special chars)
                label = re.sub(r'[^A-Za-z0-9]+', '_', visible_text_normalized[:50])
                self.screenshot_mgr.capture_rf_window(
                    self.page,
                    f"error_{label}",
                    f"Error: {visible_text_normalized[:80]}"
                )
                rf_log(f"❌ Error detected: {visible_text_normalized[:100]}")
                return True, visible_text_normalized

            # Check for info/warnings (not errors)
            if "info" in visible_text_lower or "warning" in visible_text_lower:
                label = re.sub(r'[^A-Za-z0-9]+', '_', visible_text_normalized[:50])
                self.screenshot_mgr.capture_rf_window(
                    self.page,
                    f"info_{label}",
                    f"Info: {visible_text_normalized[:80]}"
                )
                rf_log(f"ℹ️ Info message: {visible_text_normalized[:100]}")
                return False, visible_text_normalized

        except Exception as e:
            rf_log(f"⚠️ Error checking failed: {e}")

        return False, None


# ============================================================================
# HIGH-LEVEL WORKFLOWS - Built from primitives
# ============================================================================

class RFWorkflows:

    def __init__(self, primitives: RFPrimitives):
        """
        Args:
            primitives: The RFPrimitives instance to use
        """
        self.rf = primitives
        self._last_scanned_selector: Optional[str] = None

    def _is_invalid_test_data(self, msg: Optional[str]) -> bool:
        """Whether the message matches the invalid test data sentinel."""
        if not msg:
            return False
        return msg.strip().casefold() == self.rf.INVALID_TEST_DATA_MSG.casefold()

    def navigate_to_screen(self, path: list[tuple[str, str]]):

        self.rf.go_home()

        for choice, label in path:
            has_error, msg = self.rf.select_menu_option(choice, label)
            if has_error:
                raise RuntimeError(f"Navigation failed at {label}: {msg}")

    def navigate_to_menu_by_search(
        self,
        search_term: str,
        expected_tran_id: Optional[str] = None,
        option_number: str = "1"
    ) -> bool:
        rf = self.rf

        import re
        slug = re.sub(r'[^A-Za-z0-9]+', '_', search_term).strip('_') or "menu"

        rf.go_home()
        rf.press_key("Control+f", "rf_menu_search", "Opened menu search", wait_for_change=False)

        has_error, msg = rf.fill_and_submit(
            selector="input[type='text']:visible",
            value=search_term,
            screenshot_label=f"menu_search_{slug}",
            screenshot_text=f"Searched for {search_term}",
            wait_for_change=False
        )
        if has_error:
            rf_log(f"❌ Menu search failed: {msg}")
            rf.screenshot_mgr.capture_rf_window(
                rf.page,
                f"menu_search_{slug}_failed",
                f"{search_term} search failed"
            )
            return False

        if expected_tran_id:
            expected_tran = expected_tran_id if expected_tran_id.startswith("#") else f"#{expected_tran_id}"
            try:
                menu_text = rf.read_field(
                    "body",
                    transform=lambda text: " ".join(text.split())
                )
            except Exception as exc:
                rf_log(f"⚠️ Failed to read menu text: {exc}")
                rf.screenshot_mgr.capture_rf_window(
                    rf.page,
                    f"menu_tran_read_error_{slug}",
                    "Unable to read menu text"
                )
                return False

            if expected_tran not in menu_text:
                rf_log(f"❌ Expected tran id {expected_tran} not found in menu results.")
                rf.screenshot_mgr.capture_rf_window(
                    rf.page,
                    f"menu_tran_mismatch_{slug}",
                    f"Expected {expected_tran} in menu results"
                )
                return False

        has_error, msg = rf.fill_and_submit(
            selector="input[type='text']:visible",
            value=option_number,
            screenshot_label=f"menu_select_{slug}",
            screenshot_text=f"Selected {search_term} option"
        )
        if has_error:
            rf_log(f"❌ Selecting {search_term} option failed: {msg}")
            return False

        rf_log(f"✅ Navigated to {search_term}")
        return True

    def scan_barcode(
        self,
        selector: str,
        value: str,
        label: str,
        timeout: int = 2000
    ) -> tuple[bool, Optional[str]]:

        self.rf.fill_field(
            selector=selector,
            value=value,
            screenshot_label=f"scan_{label}_{value}",
            screenshot_text=f"Scanned {label}: {value}",
            timeout=timeout
        )

        self._last_scanned_selector = selector

        return False, None

    def scan_barcode_auto_enter(
        self,
        selector: str,
        value: str,
        label: str,
        timeout: int = 2000,
        auto_accept_errors: bool = True
    ) -> tuple[bool, Optional[str]]:
        # Auto-enter flows shouldn't leave stale selectors
        self._last_scanned_selector = None

        has_error, msg = self.rf.fill_and_submit(
            selector=selector,
            value=value,
            screenshot_label=f"scan_{label}_{value}",
            screenshot_text=f"Scanned {label}: {value}",
            timeout=timeout
        )

        if auto_accept_errors and msg and not self._is_invalid_test_data(msg):
            self.rf.accept_message()

        return has_error, msg

    def press_enter(
        self,
        label: str,
        wait_for_change: bool = True,
        auto_accept_errors: bool = False,
        timeout: int = 2000
    ) -> tuple[bool, Optional[str]]:

        target_selector = self._last_scanned_selector
        if not target_selector:
            rf_log("⚠️ press_enter called without a tracked input; defaulting to focused field.")

        has_error, msg = self.rf.submit_current_input(
            screenshot_label=f"press_enter_{label}",
            screenshot_text=f"Pressed Enter ({label})",
            wait_for_change=wait_for_change,
            timeout=timeout,
            selector=target_selector
        )

        self._last_scanned_selector = None

        if auto_accept_errors and msg:
            self.rf.accept_message()

        return has_error, msg

    def scan_fields_and_submit(
        self,
        scans: list[tuple[str, str, str]],
        submit_label: str,
        wait_for_change: bool = True
    ) -> tuple[bool, Optional[str]]:
 
        for selector, value, label in scans:
            has_error, msg = self.scan_barcode(selector, value, label)
            if has_error:
                rf_log(f"❌ {label} entry failed: {msg}")
                return True, msg
        else:
            has_error, msg = self.press_enter(submit_label, wait_for_change=wait_for_change)
            if has_error:
                rf_log(f"❌ Submission failed: {msg}")

        return has_error, msg

    def enter_quantity(
        self,
        selector: str,
        qty: int,
        item_name: str = "",
        timeout: int = 1000,
        auto_accept_errors: bool = True
    ) -> bool:
        label = f"qty_{item_name}_{qty}" if item_name else f"qty_{qty}"
        unit = "Unit" if qty == 1 else "Units"

        has_error, msg = self.rf.fill_and_submit(
            selector=selector,
            value=str(qty),
            screenshot_label=label,
            screenshot_text=f"Entered {qty} {unit}",
            timeout=timeout
        )

        if auto_accept_errors and msg:
            self.rf.accept_message()

        return not has_error

    def confirm_location(
        self,
        selector: str,
        location: str,
        timeout: int = 3000
    ) -> tuple[bool, Optional[str]]:
 
        return self.rf.fill_and_submit(
            selector=selector,
            value=location,
            screenshot_label=f"location_{location}",
            screenshot_text=f"Confirmed Location: {location}",
            timeout=timeout
        )


# ============================================================================
# INTEGRATION WITH EXISTING RF_MENU
# ============================================================================

class RFMenuIntegration:

    def __init__(self, rf_menu_manager):

        self.rf_menu = rf_menu_manager

        # Create primitives using existing managers
        self.primitives = RFPrimitives(
            page=rf_menu_manager.page,
            get_iframe_func=rf_menu_manager.get_iframe,
            screenshot_mgr=rf_menu_manager.screenshot_mgr,
            reset_to_home=rf_menu_manager.reset_to_home
        )

        # Create workflows
        self.workflows = RFWorkflows(self.primitives)

    def get_primitives(self) -> RFPrimitives:
        return self.primitives

    def get_workflows(self) -> RFWorkflows:
        return self.workflows
