"""
RF Primitives - Reusable building blocks for ALL RF operations.

This module provides low-level, composable functions that eliminate code duplication.
Every RF operation should be built by combining these primitives.
"""
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
        prev_hash = HashUtils.get_frame_hash(rf_iframe) if wait_for_change else None

        # Submit
        input_field.press("Enter")

        # Wait for screen change
        screen_changed = True
        if wait_for_change:
            screen_changed = WaitUtils.wait_for_screen_change(self.get_iframe, prev_hash)

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
        """
        Fill an input field without submitting. Useful when multiple fields
        need values before pressing Enter once.
        """
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
        """
        Press Enter on whichever RF input currently has focus, or on a provided selector.

        Useful when multiple fields were filled individually and now need
        to be submitted together (e.g., quantity + license plate). The optional
        selector parameter ensures we target a specific input even if focus
        moved elsewhere.
        """
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

        prev_hash = HashUtils.get_frame_hash(rf_iframe) if wait_for_change else None
        target_input.press("Enter")

        if wait_for_change:
            WaitUtils.wait_for_screen_change(self.get_iframe, prev_hash)

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
        """
        Read a value from the screen.

        Args:
            selector: CSS selector for the field
            timeout: How long to wait for field
            transform: Optional function to transform the value

        Returns:
            The field value

        Example:
            # Read location and remove dashes
            loc = primitives.read_field("span#locnField", transform=lambda x: x.replace('-', ''))
        """
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
        """
        Select a menu option by number (like pressing "1" for Inbound).

        Args:
            choice: The number to enter
            label: Label for screenshot
            timeout: How long to wait for input field

        Returns:
            (has_error, error_message)

        Example:
            primitives.select_menu_option("1", "Inbound")
        """
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
        """
        Press a keyboard shortcut (Ctrl+B, Ctrl+A, etc.).

        Args:
            key: Playwright key string (e.g., "Control+b")
            screenshot_label: Label for screenshot
            screenshot_text: Text overlay (defaults to f"Pressed {key}")
            wait_for_change: Whether to wait for screen change

        Example:
            primitives.press_key("Control+b", "RF_HOME", "Navigated to Home")
        """
        rf_iframe = self.get_iframe()

        prev_hash = HashUtils.get_frame_hash(rf_iframe) if wait_for_change else None

        self.page.keyboard.press(key)

        if wait_for_change:
            WaitUtils.wait_for_screen_change(self.get_iframe, prev_hash)

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
        """
        Check for error/info, take screenshot, accept it, and continue.
        Returns True if there was an error, False otherwise.
        """
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
    """
    High-level workflows built by combining primitives.
    These are common patterns that appear across multiple operations.
    """

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
        auto_accept_errors: bool = False
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
        """
        Fill multiple fields (without submitting) and press Enter once at the end.

        Args:
            scans: List of (selector, value, label) tuples to scan.
            submit_label: Label used for screenshots/logging when submitting.
            wait_for_change: Whether to wait for a screen change after pressing Enter.
        """
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
        timeout: int = 1000
    ) -> bool:
        """
        Enter a quantity value.

        Args:
            selector: CSS selector for the quantity input
            qty: Quantity to enter
            item_name: Optional item name for screenshot label
            timeout: How long to wait for the field

        Returns:
            True if successful (no error), False if error

        Example:
            success = workflows.enter_quantity("input#qtyInput", 10, "ABC123")
        """
        label = f"qty_{item_name}_{qty}" if item_name else f"qty_{qty}"
        unit = "Unit" if qty == 1 else "Units"

        has_error, _ = self.rf.fill_and_submit(
            selector=selector,
            value=str(qty),
            screenshot_label=label,
            screenshot_text=f"Entered {qty} {unit}",
            timeout=timeout
        )

        return not has_error

    def confirm_location(
        self,
        selector: str,
        location: str,
        timeout: int = 3000
    ) -> tuple[bool, Optional[str]]:
        """
        Confirm a putaway/destination location.

        Args:
            selector: CSS selector for the location input
            location: Location to confirm
            timeout: How long to wait for the field

        Returns:
            (has_error, error_message)

        Example:
            workflows.confirm_location("input#destLocn", "A-01-01")
        """
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
    """
    Bridge between your existing RFMenuManager and the new primitives.
    This lets you gradually migrate without breaking existing code.
    """

    def __init__(self, rf_menu_manager):
        """
        Args:
            rf_menu_manager: Your existing RFMenuManager instance
        """
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
        """Get the primitives instance."""
        return self.primitives

    def get_workflows(self) -> RFWorkflows:
        """Get the workflows instance."""
        return self.workflows
