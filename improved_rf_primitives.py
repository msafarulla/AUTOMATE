"""
Enhanced RF Primitives with shared menu navigation logic
"""
from typing import Optional, Callable, Any
from playwright.sync_api import Page, Frame
from core.screenshot import ScreenshotManager
from utils.hash_utils import HashUtils
from utils.wait_utils import WaitUtils
from core.logger import rf_log


class RFPrimitives:
    """Low-level RF terminal operations"""

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

    # ... (keep all existing primitive methods) ...

    def fill_and_submit(self, selector: str, value: str, screenshot_label: str,
                       screenshot_text: Optional[str] = None, wait_for_change: bool = True,
                       check_errors: bool = True, timeout: int = 2000) -> tuple[bool, Optional[str]]:
        """Fill input field and submit"""
        # (existing implementation)
        pass

    def read_field(self, selector: str, timeout: int = 5000,
                  transform: Optional[Callable[[str], str]] = None) -> str:
        """Read a field value"""
        # (existing implementation)
        pass

    def press_key(self, key: str, screenshot_label: str,
                 screenshot_text: Optional[str] = None, wait_for_change: bool = True):
        """Press a keyboard shortcut"""
        # (existing implementation)
        pass

    def go_home(self):
        """Navigate to RF home screen"""
        # (existing implementation)
        pass


class RFWorkflows:
    """High-level workflows built from primitives"""

    def __init__(self, primitives: RFPrimitives):
        self.rf = primitives
        self._last_scanned_selector: Optional[str] = None

    def navigate_to_menu_by_search(
        self,
        search_term: str,
        expected_tran_id: Optional[str] = None,
        option_number: str = "1"
    ) -> bool:
        """
        Navigate to an RF menu item using Ctrl+F search.
        
        This replaces the duplicated navigation code in receive.py and loading.py.
        
        Args:
            search_term: Text to search for (e.g., "RDC: Recv", "Load Trailer")
            expected_tran_id: Optional transaction ID to verify (e.g., "1012408")
            option_number: Which option to select (default "1")
            
        Returns:
            True if navigation successful, False otherwise
            
        Example:
            workflows.navigate_to_menu_by_search("RDC: Recv", "1012408")
        """
        rf = self.rf
        
        # Step 1: Go home and open search
        rf.go_home()
        rf.press_key("Control+f", "rf_menu_search", "Opened menu search", wait_for_change=False)
        
        # Step 2: Search for menu item
        has_error, msg = rf.fill_and_submit(
            selector="input[type='text']:visible",
            value=search_term,
            screenshot_label=f"menu_search_{search_term.replace(' ', '_').replace(':', '')}",
            screenshot_text=f"Searched for {search_term}",
            wait_for_change=False
        )
        
        if has_error:
            rf_log(f"❌ Menu search failed: {msg}")
            rf.screenshot_mgr.capture_rf_window(
                rf.page,
                f"menu_search_{search_term.replace(' ', '_')}_failed",
                f"{search_term} search failed"
            )
            return False
        
        # Step 3: Verify transaction ID if provided
        if expected_tran_id:
            expected_tran = expected_tran_id if expected_tran_id.startswith("#") else f"#{expected_tran_id}"
            menu_text = rf.read_field(
                "body",
                transform=lambda text: " ".join(text.split())
            )
            
            if expected_tran not in menu_text:
                rf_log(f"❌ Expected tran id {expected_tran} not found in menu results.")
                rf.screenshot_mgr.capture_rf_window(
                    rf.page,
                    f"menu_tran_mismatch_{search_term.replace(' ', '_')}",
                    f"Expected {expected_tran} in menu results"
                )
                return False
        
        # Step 4: Select the option
        has_error, msg = rf.fill_and_submit(
            selector="input[type='text']:visible",
            value=option_number,
            screenshot_label=f"menu_select_{search_term.replace(' ', '_').replace(':', '')}",
            screenshot_text=f"Selected {search_term} option"
        )
        
        if has_error:
            rf_log(f"❌ Selecting {search_term} option failed: {msg}")
            return False
        
        rf_log(f"✅ Successfully navigated to {search_term}")
        return True

    # ... (keep all existing workflow methods) ...

    def scan_barcode(self, selector: str, value: str, label: str,
                    timeout: int = 2000) -> tuple[bool, Optional[str]]:
        """Scan a barcode (fill without submitting)"""
        # (existing implementation)
        pass

    def scan_barcode_auto_enter(self, selector: str, value: str, label: str,
                               timeout: int = 2000, auto_accept_errors: bool = False) -> tuple[bool, Optional[str]]:
        """Scan barcode and automatically submit"""
        # (existing implementation)
        pass

    def scan_fields_and_submit(self, scans: list[tuple[str, str, str]],
                              submit_label: str, wait_for_change: bool = True) -> tuple[bool, Optional[str]]:
        """Scan multiple fields and submit"""
        # (existing implementation)
        pass

    def enter_quantity(self, selector: str, qty: int, item_name: str = "",
                      timeout: int = 1000) -> bool:
        """Enter quantity value"""
        # (existing implementation)
        pass

    def confirm_location(self, selector: str, location: str,
                        timeout: int = 3000) -> tuple[bool, Optional[str]]:
        """Confirm location"""
        # (existing implementation)
        pass