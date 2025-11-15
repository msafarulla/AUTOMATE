from datetime import datetime, timezone
from typing import Any

from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration
from config.operations_config import OperationConfig
from core.logger import rf_log


class ReceiveOperation(BaseOperation):
    
    def execute(
        self,
        asn: str,
        item: str,
        quantity: int,
        *,
        flow_hint: str | None = None,
        auto_handle: bool = False,
    ):
        menu_cfg = OperationConfig.RECEIVE_MENU
        selectors = OperationConfig.RECEIVE_SELECTORS

        # Create integration layer to get primitives and workflows
        integration = RFMenuIntegration(self.rf_menu)
        workflows = integration.get_workflows()
        rf = integration.get_primitives()

        # Navigate via shared workflow helper
        if not workflows.navigate_to_menu_by_search(menu_cfg.search_term, menu_cfg.tran_id):
            return False

        # Scan ASN
        has_error, msg = workflows.scan_barcode_auto_enter(selectors.asn, asn, "ASN")
        if has_error:
            rf_log(f"❌ ASN scan failed: {msg}")
            return False

        # Scan item
        has_error, msg = workflows.scan_barcode_auto_enter(selectors.item, item, "Item")
        if has_error:
            rf_log(f"❌ Item scan failed: {msg}")
            return False

        # Enter quantity (1 line instead of 8!)
        success = workflows.enter_quantity(selectors.quantity, quantity, item)
        if not success:
            rf_log("❌ Quantity entry failed")
            return False

        handled = True
        if success:
            screen_state = self.inspect_receive_screen_after_qty(rf)
            detected_flow = screen_state.get("flow")
            target_flow = flow_hint
            screen_state["detected_flow"] = detected_flow
            screen_state["expected_flow"] = target_flow
            mismatch = not self._assert_receive_screen_happy_path(screen_state)
            if mismatch:
                rf_log("⚠️ Receive screen mismatch detected after quantity entry.")
                handled = self._handle_alternate_flow_after_qty(
                    rf,
                    screen_state,
                    auto_handle
                )
                if not auto_handle or not handled:
                    return False
            dest_loc = rf.read_field(
                selectors.suggested_location,
                transform=lambda x: x.replace('-', '')
            )

            # Confirm location (1 line instead of 8!)
            workflows.confirm_location(selectors.location, dest_loc)

        return success

    def inspect_receive_screen_after_qty(self, rf) -> dict[str, Any]:
        screen_text = ""
        try:
            screen_text = rf.read_field("body")
        except Exception as exc:  # pragma: no cover
            rf_log(f"⚠️ Unable to read screen body for flow detection: {exc}")

        flow_name = self._determine_flow_after_qty(screen_text)
        return {
            "screen": screen_text,
            "flow": flow_name
        }

    def _assert_receive_screen_happy_path(self, screen_state: dict[str, Any]) -> bool:
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
        rf_log(f"Screen snapshot: {screen_state.get('screen', '')[:120]}")
        rf_log(f"Suggested location text: {screen_state.get('suggested')}")
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

    def _determine_flow_after_qty(self, screen_text: str) -> str:
        lower_screen = screen_text.lower()
        metadata = OperationConfig.RECEIVE_FLOW_METADATA
        for flow_name, flow_meta in metadata.items():
            if flow_name == "UNKNOWN":
                continue
            if self._matches_flow_meta(flow_meta, lower_screen):
                return flow_name
        return "UNKNOWN"

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
            return True
        rf_log("⚠️ Searched selectors did not locate the IB rule blind ILPN input.")
        return False


def _current_lpn_timestamp() -> str:
    """Use the local wall clock to generate the YYMMDDHHMMSS string for LPN prompts."""
    try:
        return datetime.now(timezone.utc).astimezone().strftime("%y%m%d%H%M%S")
    except Exception:
        return datetime.now().strftime("%y%m%d%H%M%S")
