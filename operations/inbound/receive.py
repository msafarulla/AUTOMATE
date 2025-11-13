from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration
from core.logger import rf_log


class ReceiveOperation(BaseOperation):
    """
    Refactored receive operation using reusable primitives.

    Compare this to the old receive.py - notice how much shorter and clearer it is!
    """

    def execute(self, asn: str, item: str, quantity: int):
        # Create integration layer to get primitives and workflows
        integration = RFMenuIntegration(self.rf_menu)
        workflows = integration.get_workflows()
        rf = integration.get_primitives()

        # Navigate to receive screen via Ctrl+F search
        rf.go_home()
        rf.press_key("Control+f", "rf_menu_search", "Opened menu search", wait_for_change=False)

        search_target, tran_id = "RDC: Recv", "1012408"
        has_error, msg = rf.fill_and_submit(
            selector="input[type='text']:visible",
            value=search_target,
            screenshot_label="menu_search_rdc_recv",
            screenshot_text=f"Searched for {search_target}",
            wait_for_change=False
        )
        if has_error:
            rf_log(f"❌ Menu search failed: {msg}")
            rf.screenshot_mgr.capture_rf_window(
                rf.page,
                "menu_search_rdc_recv_failed",
                f"{search_target} search failed"
            )
            return False

        if tran_id:
            expected_tran = tran_id if tran_id.startswith("#") else f"#{tran_id}"
            menu_text = rf.read_field(
                "body",
                transform=lambda text: " ".join(text.split())
            )
            if expected_tran not in menu_text:
                rf_log(f"❌ Expected tran id {expected_tran} not found in menu results.")
                rf.screenshot_mgr.capture_rf_window(
                    rf.page,
                    "menu_tran_mismatch_rdc_recv",
                    f"Expected {expected_tran} in menu results"
                )
                return False

        has_error, msg = rf.fill_and_submit(
            selector="input[type='text']:visible",
            value="1",
            screenshot_label="menu_select_rdc_recv",
            screenshot_text=f"Selected {search_target} option"
        )
        if has_error:
            rf_log(f"❌ Selecting RDC: Recv option failed: {msg}")
            return False

        # Scan ASN (1 line instead of 8!)
        has_error, msg = workflows.scan_barcode_auto_enter("input#shipinpId", asn, "ASN")
        if has_error:
            rf_log(f"❌ ASN scan failed: {msg}")
            return False

        # Scan item (1 line instead of 8!)
        has_error, msg = workflows.scan_barcode_auto_enter("input#verfiyItemBrcd", item, "Item")
        if has_error:
            rf_log(f"❌ Item scan failed: {msg}")
            return False

        # Enter quantity (1 line instead of 8!)
        success = workflows.enter_quantity("input#input1input2", quantity, item)
        if not success:
            rf_log("❌ Quantity entry failed")
            return False

        if success:
            # Read suggested location (1 line instead of 5!)
            dest_loc = rf.read_field(
                "span#dataForm\\:SBRUdtltxt1_b1",
                transform=lambda x: x.replace('-', '')
            )

            # Confirm location (1 line instead of 8!)
            workflows.confirm_location("input#dataForm\\:locn", dest_loc)

        return success
