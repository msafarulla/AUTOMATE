import re

from datetime import datetime, timezone
from typing import Any

from ui.navigation import NavigationManager

from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration
from config.operations_config import OperationConfig
from core.logger import rf_log


class ReceiveOperation(BaseOperation):

    def __init__(self, page, page_mgr, screenshot_mgr, rf_menu):
        super().__init__(page, page_mgr, screenshot_mgr, rf_menu)
        integration = RFMenuIntegration(self.rf_menu)
        self.rf = integration.get_primitives()
        self.workflows = integration.get_workflows()
        self.menu_cfg = OperationConfig.RECEIVE_MENU
        self.selectors = OperationConfig.RECEIVE_SELECTORS
    
    def execute(
        self,
        asn: str,
        item: str,
        quantity: int,
        *,
        flow_hint: str | None = None,
        auto_handle: bool = False,
        tasks_cfg: dict[str, Any] | None = None,
    ):
        if not self._navigate_to_receive_menu():
            return False

        if not self._scan_identifiers(asn, item):
            return False

        if not self._log_quantities():
            return False

        success = self.workflows.enter_quantity(self.selectors.quantity, quantity, item)
        if not success:
            rf_log("❌ Quantity entry failed")
            return False

        return self._handle_post_quantity_flow(asn, item, quantity, flow_hint, tasks_cfg, auto_handle)

    def _navigate_to_receive_menu(self) -> bool:
        return self.workflows.navigate_to_menu_by_search(self.menu_cfg.search_term, self.menu_cfg.tran_id)

    def _scan_identifiers(self, asn: str, item: str) -> bool:
        has_error, msg = self.workflows.scan_barcode_auto_enter(self.selectors.asn, asn, "ASN")
        if has_error:
            rf_log(f"❌ ASN scan failed: {msg}")
            return False
        has_error, msg = self.workflows.scan_barcode_auto_enter(self.selectors.item, item, "Item")
        if has_error:
            rf_log(f"❌ Item scan failed: {msg}")
            return False
        return True

    def _log_quantities(self) -> bool:
        shipped_qty, received_qty = self._read_quantities_from_body(self.rf)
        ref = lambda v: v if v is not None else "unknown"
        rf_log(f"ℹ️ Screen reports shipped={ref(shipped_qty)}; received={ref(received_qty)}")
        return True

    def _handle_post_quantity_flow(
        self,
        asn: str,
        item: str,
        quantity: int,
        flow_hint: str | None,
        tasks_cfg: dict[str, Any] | None,
        auto_handle: bool
    ) -> bool:
        if not self._maybe_run_tasks_ui(tasks_cfg):
            return False

        screen_state = self.inspect_receive_screen_after_qty(self.rf, flow_hint)
        detected_flow = screen_state.get("flow")
        target_flow = flow_hint
        screen_state["detected_flow"] = detected_flow
        screen_state["expected_flow"] = target_flow
        mismatch = not self._assert_receive_screen_flow_hint(screen_state)
        if mismatch:
            rf_log("⚠️ Receive screen mismatch detected after quantity entry.")
            handled = self._handle_alternate_flow_after_qty(
                self.rf,
                screen_state,
                auto_handle
            )
            if not auto_handle or not handled:
                return False
            return True

        dest_loc = self._read_suggested_location(self.rf, self.selectors)
        self.workflows.confirm_location(self.selectors.location, dest_loc)
        self.screenshot_mgr.capture_rf_window(
            self.page,
            "receive_summary",
            f"ASN {asn} received {quantity} {'Units' if quantity > 1 else 'Unit'} of {item}"
        )
        return True

    def inspect_receive_screen_after_qty(self, rf, flow_hint: str | None) -> dict[str, Any]:
        screen_text = ""
        try:
            screen_text = rf.read_field("body")
        except Exception as exc:  # pragma: no cover
            rf_log(f"⚠️ Unable to read screen body for flow detection: {exc}")

        flow_name = self._determine_flow_after_qty(screen_text, flow_hint)
        return {
            "screen": screen_text,
            "flow": flow_name
        }

    def _read_suggested_location(self, rf, selectors) -> str:
        candidate_selectors = self._suggested_location_candidates(selectors)
        if not candidate_selectors:
            rf_log("⚠️ Suggested location selectors are not configured.")
            return ""

        for selector in candidate_selectors:
            try:
                raw = rf.read_field(selector, transform=lambda t: " ".join(t.split()))
            except Exception:
                continue
            if raw:
                cleaned = raw.replace("-", "").strip()
                if cleaned:
                    return cleaned

        # Fallback to parsing body text
        try:
            body_text = rf.read_field("body")
        except Exception as exc:
            rf_log(f"⚠️ Unable to read RF body text for suggested location: {exc}")
            return ""

        location = self._extract_suggested_location(body_text)
        if location:
            return location

        body_preview = " ".join(body_text.split())[:120]
        rf_log(f"⚠️ Unable to resolve suggested location from RF screen. Preview: '{body_preview}'")
        return ""

    def _suggested_location_candidates(self, selectors) -> list[str]:
        keys = (
            "suggested_location_aloc",
            "suggested_location_cloc",
        )
        candidates: list[str] = []
        for key in keys:
            selector = selectors.selectors.get(key)
            if isinstance(selector, str):
                candidates.append(selector)
        return candidates

    def _read_quantities_from_body(self, rf) -> tuple[int | None, int | None]:
        selectors = OperationConfig.RECEIVE_SELECTORS.selectors

        shipped = self._read_quantity_from_selector(rf, selectors.get("shipped_quantity"))
        received = self._read_quantity_from_selector(rf, selectors.get("received_quantity"))

        if shipped is not None or received is not None:
            return shipped, received

        try:
            body_text = rf.read_field("body")
        except Exception as exc:
            rf_log(f"⚠️ Unable to read RF body text: {exc}")
            return None, None
        shipped = self._extract_quantity_multi(body_text, [
            r"Shpd\s*:?\s*([\d,]+)",
            r"Shipped(?:\s+Qty)?[:\s]+([\d,]+)",
            r"Shipped\s+([\d,]+)",
        ])
        received = self._extract_quantity_multi(body_text, [
            r"Rcvd\s*:?\s*([\d,]+)",
            r"Received(?:\s+Qty)?[:\s]+([\d,]+)",
            r"Received\s+([\d,]+)",
        ])
        if shipped is None and received is None:
            body_preview = " ".join(body_text.split())[:120]
            rf_log(f"⚠️ Unable to parse shipped/received from RF body. Preview: '{body_preview}'")
        return shipped, received

    def _read_quantity_from_selector(self, rf, selector: str | None) -> int | None:
        if not selector:
            return None
        try:
            text = rf.read_field(selector, transform=lambda t: " ".join(t.split()))
        except Exception as exc:
            rf_log(f"⚠️ Unable to read quantity from '{selector}': {exc}")
            return None
        qty = self._extract_quantity(text, r"([\d,]+)")
        if qty is None and text:
            rf_log(f"⚠️ Selector '{selector}' returned '{text}' but no quantity was parsed.")
        return qty

    def _extract_quantity(self, text: str, pattern: str) -> int | None:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        digits = match.group(1).replace(",", "")
        try:
            return int(digits)
        except ValueError:
            return None

    def _extract_quantity_multi(self, text: str, patterns: list[str]) -> int | None:
        for pattern in patterns:
            qty = self._extract_quantity(text, pattern)
            if qty is not None:
                return qty
        return None

    def _extract_suggested_location(self, text: str) -> str:
        patterns = [
            r"ALOC\s*:?\s*([A-Za-z0-9\-]+)",
            r"CLOC\s*:?\s*([A-Za-z0-9\-]+)",
            r"Loc(?:ation)?\s*:?\s*([A-Za-z0-9\-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).replace("-", "").strip()
        return ""

    def _read_shipped_quantity(self, rf) -> int | None:
        try:
            text = rf.read_field("div#shippedQty").strip()
        except Exception as exc:
            rf_log(f"⚠️ Unable to read shipped quantity label: {exc}")
            return None
        digits = re.findall(r"\d+", text)
        if not digits:
            return None
        try:
            return int(digits[0])
        except ValueError:
            return None

    def _read_received_quantity(self, rf) -> int | None:
        try:
            text = rf.read_field("div#RecvQty").strip()
        except Exception as exc:
            rf_log(f"⚠️ Unable to read received quantity label: {exc}")
            return None
        digits = re.findall(r"\d+", text)
        if not digits:
            return None
        try:
            return int(digits[0])
        except ValueError:
            return None

    def _maybe_run_tasks_ui(self, tasks_cfg: dict[str, Any] | None) -> bool:
        """Open the Tasks UI mid-flow if the workflow configuration requests it."""
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

        focus_title = "RF Menu"
        nav_mgr.close_active_windows(skip_titles=[focus_title])
        if not nav_mgr.focus_window_by_title(focus_title):
            rf_log("⚠️ Unable to bring RF Menu back to foreground after tasks detour.")
            return False

        rf_log(f"ℹ️ {operation_note}")
        return True

    def _assert_receive_screen_flow_hint(self, screen_state: dict[str, Any]) -> bool:
        detected_flow = screen_state.get("detected_flow")
        expected_flow = screen_state.get("expected_flow")
        assert detected_flow is not None
        assert expected_flow is not None
        return detected_flow == expected_flow

    def _handle_alternate_flow_after_qty(
        self,
        rf,
        screen_state: dict[str, Any],
        auto_handle: bool,
    ) -> bool:
        rf_log("⚠️ Receive screen guard triggered alternate flow helper.")
        detected_flow = screen_state.get("detected_flow") or screen_state.get("flow")
        expected_flow = screen_state.get("expected_flow") or detected_flow
        rf_log(f"Detected flow: {detected_flow}")
        rf_log(f"Expected flow: {expected_flow}")
        # rf_log(f"Screen snapshot: {screen_state.get('screen', '')[:120]}")
        meta = self._flow_metadata(detected_flow)
        rf_log(f"Flow policy: {meta.get('description')}")
        deviation_snippet = screen_state.get("screen", "").strip().replace("\n", " ")[:80]
        screenshot_label = f"receive_flow_{detected_flow.lower()}"
        screenshot_text = f"Flow {detected_flow} (auto_handle={auto_handle}): {deviation_snippet}"
        self.screenshot_mgr.capture_rf_window(
            self.page,
            screenshot_label,
            screenshot_text,
        )
        if not auto_handle:
            rf_log("⚠️ Flow policy signals abort; stopping receive.")
            return False
        handler_result = False
        if detected_flow == "IB_RULE_EXCEPTION_BLIND_ILPN":
            handler_result = self._handle_ib_rule_exception_blind_ilpn(rf)
        else:
            rf_log("⚠️ Auto-handler not implemented for this flow.")
        return handler_result

    def _flow_metadata(self, flow_name: str) -> dict[str, Any]:
        flows = OperationConfig.RECEIVE_FLOW_METADATA
        default = flows.get("UNKNOWN", {})
        return flows.get(flow_name, default)

    def _determine_flow_after_qty(self, screen_text: str, flow_hint: str | None) -> str:
        lower_screen = screen_text.lower()
        metadata = OperationConfig.RECEIVE_FLOW_METADATA
        for flow_name, flow_meta in metadata.items():
            if flow_name == "UNKNOWN":
                continue
            if self._matches_flow_meta(flow_meta, lower_screen):
                return flow_name
        return flow_hint or "UNKNOWN"

    def _matches_flow_meta(self, meta: dict[str, Any], lower_screen: str) -> bool:
        keywords = meta.get("keywords")
        if keywords:
            if not any(keyword in lower_screen for keyword in keywords):
                return False
        return True

    def _handle_ib_rule_exception_blind_ilpn(self, rf) -> bool:
        timestamp = _current_lpn_timestamp()
        selectors = (
            OperationConfig.RECEIVE_DEVIATION_SELECTORS.lpn_input,
            OperationConfig.RECEIVE_DEVIATION_SELECTORS.lpn_input_name,
        )
        for selector in selectors:
            try:
                has_error, msg = rf.fill_and_submit(
                    selector,
                    timestamp,
                    "receive_ib_rule_lpn",
                    "Entered generated LPN for IB rule exception",
                )
            except Exception as exc:
                rf_log(f"⚠️ Unable to interact with LPN input '{selector}': {exc}")
                continue
            if has_error:
                rf_log(f"❌ IB rule blind ILPN handler failed for '{selector}': {msg or 'unknown error'}")
                return False
            self.screenshot_mgr.capture_rf_window(
                self.page,
                "receive_ib_rule_lpn_success",
                "Entered generated LPN for IB rule exception"
            )
            return True
        rf_log("⚠️ Searched selectors did not locate the IB rule blind ILPN input.")
        return False


def _current_lpn_timestamp() -> str:
    """Use the local wall clock to generate the YYMMDDHHMMSS string for LPN prompts."""
    try:
        return datetime.now(timezone.utc).astimezone().strftime("%y%m%d%H%M%S")
    except Exception:
        return datetime.now().strftime("%y%m%d%H%M%S")
