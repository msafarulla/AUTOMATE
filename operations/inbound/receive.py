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