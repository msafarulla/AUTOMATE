from operations.base_operation import BaseOperation
from utils.hash_utils import HashUtils
from utils.wait_utils import WaitUtils


class ReceiveOperation(BaseOperation):
    def execute(self, asn: str, item: str, quantity: int):
        """Execute ASN receiving workflow"""
        # Navigate to receive screen
        self.rf_menu.reset_to_home()
        self.rf_menu.enter_choice("1", "Inbound")
        self.rf_menu.enter_choice("1", "RDC Recv ASN")

        # Enter ASN
        self._enter_asn(asn)

        # Enter item
        self._enter_item(item)

        # Enter quantity
        success = self._enter_quantity(quantity)

        if success:
            # Handle putaway if needed
            dest_loc = self._get_prompted_location()
            if dest_loc:
                self._enter_destination(dest_loc)

        return success

    def _enter_asn(self, asn: str):
        rf_iframe = self.rf_menu.get_iframe()
        asn_input = rf_iframe.locator("input#shipinpId")
        asn_input.wait_for(state="visible", timeout=1500)
        asn_input.fill(asn)

        prev_hash = HashUtils.get_frame_hash(rf_iframe)
        self.screenshot_mgr.capture_rf_window(self.page, f"asn_{asn}", f"Scanned ASN {asn}")
        asn_input.press("Enter")
        WaitUtils.wait_for_screen_change(self.rf_menu.get_iframe, prev_hash)
        self.handle_error_screen(rf_iframe)

    def _enter_item(self, item: str):
        rf_iframe = self.rf_menu.get_iframe()
        item_input = rf_iframe.locator("input#verfiyItemBrcd")
        item_input.wait_for(state="visible", timeout=1500)
        self.item_name = item
        item_input.fill(item)
        self.screenshot_mgr.capture_rf_window(self.page, f"item_{item}", f"Scanned Item {item}")
        prev_hash = HashUtils.get_frame_hash(rf_iframe)
        item_input.press("Enter")
        WaitUtils.wait_for_screen_change(self.rf_menu.get_iframe, prev_hash)
        self.handle_error_screen(rf_iframe)

    def _enter_quantity(self, qty: int) -> bool:
        rf_iframe = self.rf_menu.get_iframe()
        qty_input = rf_iframe.locator("input#input1input2")
        qty_input.wait_for(state="visible", timeout=1000)
        qty_input.fill(str(qty))
        self.screenshot_mgr.capture_rf_window(self.page, f"Entered SKU {self.item_name}, {qty} {'Units' if qty >1 else 'Unit'}", f"Entered {qty} {'Units' if qty >1 else 'Unit'}")
        prev_hash = HashUtils.get_frame_hash(rf_iframe)
        qty_input.press("Enter")
        WaitUtils.wait_for_screen_change(self.rf_menu.get_iframe, prev_hash)
        has_error, msg = self.handle_error_screen(rf_iframe)
        return not has_error

    def _get_prompted_location(self) -> str:
        rf_iframe = self.rf_menu.get_iframe()
        locator = rf_iframe.locator("span#dataForm\\:SBRUdtltxt1_b1")
        locator.wait_for(state="visible", timeout=5000)
        value = locator.inner_text().strip()
        return value.replace('-', '')

    def _enter_destination(self, dest_loc: str):
        rf_iframe = self.rf_menu.get_iframe()
        dest_input = rf_iframe.locator("input#dataForm\\:locn")
        dest_input.wait_for(state="visible", timeout=3000)
        dest_input.fill(dest_loc)
        self.screenshot_mgr.capture_rf_window(self.page, f"dest_{dest_loc}", f"Scanned Dest {dest_loc}")
        prev_hash = HashUtils.get_frame_hash(rf_iframe)
        dest_input.press("Enter")
        WaitUtils.wait_for_screen_change(self.rf_menu.get_iframe, prev_hash)
        self.handle_error_screen(rf_iframe)
