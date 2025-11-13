from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration
from core.logger import rf_log


class LoadingOperation(BaseOperation):
    """
    Refactored receive operation using reusable primitives.

    Compare this to the old receive.py - notice how much shorter and clearer it is!
    """

    def execute(self, shipment: str, dockDoor: str, BOL: str):

        # Create integration layer to get primitives and workflows
        integration = RFMenuIntegration(self.rf_menu)
        workflows = integration.get_workflows()
        rf = integration.get_primitives()

        # Navigate to Load Trailer via Ctrl+F search
        search_target, tran_id = "Load Trailer", "1012334"

        rf.go_home()
        rf.press_key("Control+f", "rf_menu_search", "Opened menu search", wait_for_change=False)

        has_error, msg = rf.fill_and_submit(
            selector="input[type='text']:visible",
            value=search_target,
            screenshot_label="menu_search_load_trailer",
            screenshot_text=f"Searched for {search_target}",
            wait_for_change=False
        )
        if has_error:
            rf_log(f"❌ Menu search failed: {msg}")
            return False

        if tran_id:
            expected_tran = tran_id if tran_id.startswith("#") else f"#{tran_id}"
            menu_text = rf.read_field(
                "body",
                transform=lambda text: " ".join(text.split())
            )
            if expected_tran not in menu_text:
                rf_log(f"❌ Expected tran id {expected_tran} not found in menu results.")
                return False

        has_error, msg = rf.fill_and_submit(
            selector="input[type='text']:visible",
            value="1",
            screenshot_label="menu_select_load_trailer",
            screenshot_text=f"Selected {search_target} option"
        )
        if has_error:
            rf_log(f"❌ Selecting {search_target} option failed: {msg}")
            return False

        scans = [
            ("input#barcode20", shipment, "Shipment Id"),
            ("input#barcode13", dockDoor, "Dock Door"),
            ("input#barcode32", BOL, "BOL")
        ]

        has_error, msg = workflows.scan_fields_and_submit(scans, "load_trailer")
        if has_error:
            return False
        return True
