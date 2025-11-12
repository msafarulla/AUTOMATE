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

        # Navigate to receive screen (2 lines instead of 6!)
        workflows.navigate_to_screen([
            ("1", "Inbound"),
            ("1", "RDC Recv ASN")
        ])

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


# ============================================================================
# COMPARISON: Old vs New
# ============================================================================

"""
OLD CODE (from your receive.py):
---------------------------------

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

Total: ~30 lines of repetitive code


NEW CODE (using primitives):
-----------------------------

workflows.scan_barcode_auto_enter("input#shipinpId", asn, "ASN")
workflows.scan_barcode_auto_enter("input#verfiyItemBrcd", item, "Item")
success = workflows.enter_quantity("input#input1input2", quantity, item)

Total: 3 lines!

SAVINGS: 90% less code, infinitely more maintainable!
"""
