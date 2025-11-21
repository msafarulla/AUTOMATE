"""
Receive Operation - Handles ASN receiving workflow in RF terminal.

Flow: Navigate → Scan ASN → Scan Item → Enter Qty → Confirm Location
"""
import re
from datetime import datetime
from typing import Any

from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration
from ui.navigation import NavigationManager
from config.operations_config import OperationConfig
from core.logger import rf_log


class ReceiveOperation(BaseOperation):
    """Handles ASN receiving workflow in RF terminal."""

    def __init__(self, page, page_mgr, screenshot_mgr, rf_menu):
        super().__init__(page, page_mgr, screenshot_mgr, rf_menu)
        
        # Setup RF integration
        integration = RFMenuIntegration(rf_menu)
        self.rf = integration.get_primitives()
        self.workflows = integration.get_workflows()
        
        # Load config
        self.menu = OperationConfig.RECEIVE_MENU
        self.selectors = OperationConfig.RECEIVE_SELECTORS
        self._ilpn: str | None = None
        self._qty_context: dict[str, int | None] | None = None

    def execute(self, asn: str, item: str, quantity: int, **options) -> bool:
        """
        Execute receive operation.
        
        Args:
            asn: ASN number to receive
            item: Item barcode
            quantity: Quantity to receive
            **options: flow_hint, auto_handle
        """
        steps = [
            (self._navigate, "Navigate to receive"),
            (lambda: self._scan(asn, item), "Scan ASN/Item"),
            (lambda: self._enter_quantity(quantity, item, options), "Enter quantity"),
            (lambda: self._complete(asn, item, quantity, options), "Complete receive"),
        ]
        
        for step_fn, step_name in steps:
            if not step_fn():
                rf_log(f"❌ Failed at: {step_name}")
                return False
        return True

    # =========================================================================
    # MAIN STEPS
    # =========================================================================

    def _navigate(self) -> bool:
        """Step 1: Navigate to receive menu."""
        return self.workflows.navigate_to_menu_by_search(
            self.menu.search_term, 
            self.menu.tran_id
        )

    def _scan(self, asn: str, item: str) -> bool:
        """Step 2: Scan ASN and item barcodes."""
        scans = [
            (self.selectors.asn, asn, "ASN"),
            (self.selectors.item, item, "Item"),
        ]
        
        for selector, value, label in scans:
            has_error, msg = self.workflows.scan_barcode_auto_enter(
                selector, value, label
            )
            if has_error:
                rf_log(f"❌ {label} scan failed: {msg}")
                return False
        shipped, received, ilpn = self._log_quantities()
        self._ilpn = ilpn
        self._qty_context = {"shipped": shipped, "received": received, "ilpn": ilpn}
        return True

    def _enter_quantity(self, quantity: int, item: str, options: dict) -> bool:
        """Step 3: Enter quantity."""
        if self._qty_context:
            rf_log(
                f"ℹ️ Entering qty with context shipped={self._qty_context.get('shipped')} "
                f"received={self._qty_context.get('received')} "
                f"ilpn={self._qty_context.get('ilpn')}"
            )
        success = self.workflows.enter_quantity(
            self.selectors.quantity,
            quantity,
            item_name=item,
            context=self._qty_context,
        )

        if success:
            tasks_cfg = options.get("tasks_cfg")
            success = self._maybe_run_tasks_ui(tasks_cfg)
        return success

    def _complete(self, asn: str, item: str, quantity: int, options: dict) -> bool:
        """Step 4: Handle post-quantity flow."""
        flow_hint = options.get("flow_hint")
        auto_handle = options.get("auto_handle", False)

        # Check current screen
        detected = self._detect_flow(flow_hint)
        
        # Handle deviation if needed
        if detected != flow_hint:
            rf_log(f"⚠️ Flow mismatch: expected {flow_hint}, got {detected}")
            self._capture_deviation(detected, auto_handle)
            if not auto_handle:
                return False
            return self._handle_deviation(detected)

        # Happy path: confirm location
        location = self._read_location()
        self.workflows.confirm_location(self.selectors.location, location)
        self._capture_success(asn, item, quantity)
        return True

    # =========================================================================
    # OPTIONAL TASKS UI DETOUR
    # =========================================================================

    def _maybe_run_tasks_ui(self, tasks_cfg: dict[str, Any] | None) -> bool:
        """Open the Tasks UI mid-flow if configured."""
        if not tasks_cfg or not bool(tasks_cfg.get("enabled", True)):
            return True

        nav_mgr = NavigationManager(self.page, self.screenshot_mgr)
        search_term = tasks_cfg.get("search_term", "tasks")
        match_text = tasks_cfg.get("match_text", "Tasks (Configuration)")
        preserve_window = bool(tasks_cfg.get("preserve_window") or tasks_cfg.get("preserve"))
        close_existing = not preserve_window
        if not nav_mgr.open_tasks_ui(search_term, match_text, close_existing=close_existing):
            rf_log("❌ Tasks UI detour failed during receive flow.")
            return False

        operation_note = tasks_cfg.get("operation_note", "Visited Tasks UI during receive")
        self.screenshot_mgr.capture(
            self.page,
            "receive_tasks_ui",
            operation_note,
        )

        focus_title = tasks_cfg.get("rf_focus_title", "RF Menu")
        nav_mgr.close_active_windows(skip_titles=[focus_title])
        if not nav_mgr.focus_window_by_title(focus_title):
            rf_log("⚠️ Unable to bring RF Menu back to foreground after tasks detour.")
            return False

        rf_log(f"ℹ️ {operation_note}")
        return True

    # =========================================================================
    # FLOW DETECTION & HANDLING
    # =========================================================================

    def _detect_flow(self, default: str | None) -> str:
        """Detect current screen based on keywords."""
        try:
            body = self.rf.read_field("body").lower()
        except Exception:
            return default or "UNKNOWN"

        for name, meta in OperationConfig.RECEIVE_FLOW_METADATA.items():
            if name == "UNKNOWN":
                continue
            if any(kw in body for kw in meta.get("keywords", [])):
                return name
        
        return default or "UNKNOWN"

    def _handle_deviation(self, flow: str) -> bool:
        """Handle non-happy-path flows."""
        handlers = {
            "IB_RULE_EXCEPTION_BLIND_ILPN": self._handle_blind_ilpn,
        }
        handler = handlers.get(flow)
        if handler:
            return handler()
        rf_log(f"⚠️ No handler for flow: {flow}")
        return False

    def _handle_blind_ilpn(self) -> bool:
        """Handle IB rule exception requiring LPN entry."""
        lpn = datetime.now().strftime("%y%m%d%H%M%S")
        selectors = OperationConfig.RECEIVE_DEVIATION_SELECTORS
        
        for selector in (selectors.lpn_input, selectors.lpn_input_name):
            try:
                has_error, _ = self.rf.fill_and_submit(
                    selector, lpn, "blind_ilpn", f"Entered LPN: {lpn}"
                )
                if not has_error:
                    self.screenshot_mgr.capture_rf_window(
                        self.page, "ilpn_success", "Blind iLPN entered"
                    )
                    return True
            except Exception:
                continue
        
        rf_log("❌ Could not enter blind iLPN")
        return False

    # =========================================================================
    # HELPERS - Reading screen data
    # =========================================================================

    def _read_location(self) -> str:
        """Read suggested location from screen."""
        # Try configured selectors
        for key in ("suggested_location_aloc", "suggested_location_cloc"):
            selector = self.selectors.selectors.get(key)
            if not selector:
                continue
            try:
                loc = self.rf.read_field(selector).replace("-", "").strip()
                if loc:
                    return loc
            except Exception:
                continue

        # Fallback: parse from body
        try:
            body = self.rf.read_field("body")
            match = re.search(r"[AC]LOC\s*:?\s*([A-Za-z0-9\-]+)", body, re.I)
            if match:
                return match.group(1).replace("-", "").strip()
        except Exception:
            pass

        rf_log("⚠️ Could not read suggested location")
        return ""

    def _log_quantities(self):
        """Log shipped/received quantities (and iLPN) from screen."""
        shipped, received = self._parse_quantities()
        ilpn = self._parse_ilpn()
        rf_log(f"ℹ️ Shipped: {shipped}, Received: {received}, LPN: {ilpn}")
        return shipped, received, ilpn

    def _parse_quantities(self) -> tuple[int | None, int | None]:
        """Extract shipped/received quantities."""
        s = self.selectors.selectors
        shipped = self._read_number(s.get("shipped_quantity"))
        received = self._read_number(s.get("received_quantity"))
        
        if shipped is None and received is None:
            # Fallback: parse body text
            try:
                body = self.rf.read_field("body")
                shipped = self._extract_number(body, r"Shpd?\s*:?\s*([\d,]+)")
                received = self._extract_number(body, r"Rcvd?\s*:?\s*([\d,]+)")
            except Exception:
                pass
        return shipped, received

    def _parse_ilpn(self) -> str | None:
        """Extract iLPN from screen or body."""
        sel = self.selectors.selectors
        ilpn_selector = sel.get("ilpn") or sel.get("ilpn_hidden")
        if ilpn_selector:
            try:
                text = self.rf.read_field(ilpn_selector)
                ilpn = self._extract_lpn(text)
                if ilpn:
                    return ilpn
            except Exception:
                pass

        try:
            body = self.rf.read_field("body")
            ilpn = self._extract_lpn(body)
            if ilpn:
                return ilpn
        except Exception:
            pass
        return None

    def _read_number(self, selector: str | None) -> int | None:
        """Read number from selector."""
        if not selector:
            return None
        try:
            text = self.rf.read_field(selector)
            return self._extract_number(text, r"([\d,]+)")
        except Exception:
            return None

    def _extract_number(self, text: str, pattern: str) -> int | None:
        """Extract first number matching pattern."""
        match = re.search(pattern, text, re.I)
        if match:
            try:
                return int(match.group(1).replace(",", ""))
            except ValueError:
                pass
        return None

    def _extract_lpn(self, text: str) -> str | None:
        """Extract LPN/id from provided text."""
        patterns = [
            r"\bLPN[:\s\"]*([A-Za-z0-9]+)",
            r"\bcaseinpid\b.*?value=\"([A-Za-z0-9]+)\"",
        ]
        normalized = " ".join(text.split())
        for pattern in patterns:
            match = re.search(pattern, normalized, re.I)
            if match:
                return match.group(1).strip()
        return None

    # =========================================================================
    # HELPERS - Screenshots
    # =========================================================================

    def _capture_success(self, asn: str, item: str, qty: int):
        """Capture success screenshot."""
        unit = "Unit" if qty == 1 else "Units"
        self.screenshot_mgr.capture_rf_window(
            self.page, "receive_complete",
            f"ASN {asn}: {qty} {unit} of {item}"
        )

    def _capture_deviation(self, flow: str, auto_handle: bool):
        """Capture deviation screenshot."""
        self.screenshot_mgr.capture_rf_window(
            self.page, f"deviation_{flow.lower()}",
            f"Flow: {flow} (auto_handle={auto_handle})"
        )
