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

        if success:
            screen_state = self.inspect_receive_screen_after_qty(rf, selectors)
            detected_flow = screen_state.get("flow")
            target_flow = flow_hint or detected_flow
            screen_state["flow"] = target_flow
            if not self._assert_receive_screen_happy_path(screen_state):
                rf_log("⚠️ Receive screen mismatch detected after quantity entry.")
                return self._handle_alternate_flow_after_qty(
                    rf,
                    selectors,
                    screen_state,
                    auto_handle
                )
            dest_loc = rf.read_field(
                selectors.suggested_location,
                transform=lambda x: x.replace('-', '')
            )

            # Confirm location (1 line instead of 8!)
            workflows.confirm_location(selectors.location, dest_loc)

        return success

    def inspect_receive_screen_after_qty(self, rf, selectors) -> dict[str, Any]:
        screen_text = ""
        suggested_text = ""
        try:
            screen_text = rf.read_field("body")
        except Exception as exc:  # pragma: no cover
            rf_log(f"⚠️ Unable to read screen body for flow detection: {exc}")
        try:
            suggested_text = rf.read_field(selectors.suggested_location)
        except Exception as exc:  # pragma: no cover
            rf_log(f"ℹ️ Suggested location selector missing or invisible: {exc}")

        flow_name = self._determine_flow_after_qty(screen_text, suggested_text)
        return {
            "screen": screen_text,
            "suggested": suggested_text,
            "flow": flow_name
        }

    def _assert_receive_screen_happy_path(self, screen_state: dict[str, Any]) -> bool:
        flow = screen_state.get("flow")
        meta = self._flow_metadata(flow)
        suggested = bool(screen_state.get("suggested", "").strip())
        return flow == "HAPPY_PATH" and suggested

    def _handle_alternate_flow_after_qty(
        self,
        rf,
        selectors,
        screen_state: dict[str, Any],
        auto_handle: bool,
    ) -> bool:
        rf_log("⚠️ Receive screen guard triggered alternate flow helper.")
        flow_name = screen_state.get("flow")
        rf_log(f"Flow detected: {flow_name}")
        rf_log(f"Screen snapshot: {screen_state.get('screen', '')[:120]}")
        rf_log(f"Suggested location text: {screen_state.get('suggested')}")
        meta = self._flow_metadata(screen_state.get("flow"))
        rf_log(f"Flow policy: {meta.get('description')}")
        deviation_snippet = screen_state.get("screen", "").strip().replace("\n", " ")[:80]
        screenshot_label = f"receive_flow_{flow_name.lower()}"
        screenshot_text = f"Flow {flow_name} (auto_handle={auto_handle}): {deviation_snippet}"
        self.screenshot_mgr.capture_rf_window(
            self.page,
            screenshot_label,
            screenshot_text
        )
        if not auto_handle:
            rf_log("⚠️ Flow policy signals abort; stopping receive.")
            return False
        rf_log("ℹ️ Auto-handling flow per policy (still returns False until handler is implemented).")
        # TODO: call specific handlers for each flow by name
        return False

    def _flow_metadata(self, flow_name: str) -> dict[str, Any]:
        flows = OperationConfig.RECEIVE_FLOW_METADATA
        default = flows.get("UNKNOWN", {})
        return flows.get(flow_name, default)

    def _determine_flow_after_qty(self, screen_text: str, suggested_text: str) -> str:
        lower_screen = screen_text.lower()
        lower_suggested = suggested_text.lower()
        metadata = OperationConfig.RECEIVE_FLOW_METADATA
        for flow_name, flow_meta in metadata.items():
            if flow_name == "UNKNOWN":
                continue
            if self._matches_flow_meta(flow_meta, lower_screen, lower_suggested):
                return flow_name
        return "UNKNOWN"

    def _matches_flow_meta(self, meta: dict[str, Any], lower_screen: str, lower_suggested: str) -> bool:
        keywords = meta.get("keywords")
        if keywords:
            if not any(keyword in lower_screen for keyword in keywords):
                return False
        if meta.get("requires_suggested"):
            if not lower_suggested.strip():
                return False
        return True
