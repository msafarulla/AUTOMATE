from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration
from operations_config import OperationConfig
from core.logger import rf_log


class ReceiveOperation(BaseOperation):
    """
    Refactored receive operation using reusable primitives.

    Compare this to the old receive.py - notice how much shorter and clearer it is!
    """

    def execute(self, asn: str, item: str, quantity: int):
        menu_cfg = OperationConfig.RECEIVE_MENU
        selectors = OperationConfig.RECEIVE_SELECTORS

        # Create integration layer to get primitives and workflows
        integration = RFMenuIntegration(self.rf_menu)
        workflows = integration.get_workflows()
        rf = integration.get_primitives()

        # Navigate via shared workflow helper
        if not workflows.navigate_to_menu_by_search(menu_cfg.search_term, menu_cfg.tran_id):
            return False

        # Scan ASN (1 line instead of 8!)
        has_error, msg = workflows.scan_barcode_auto_enter(selectors.asn, asn, "ASN")
        if has_error:
            rf_log(f"❌ ASN scan failed: {msg}")
            return False

        # Scan item (1 line instead of 8!)
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
            # Read suggested location (1 line instead of 5!)
            dest_loc = rf.read_field(
                selectors.suggested_location,
                transform=lambda x: x.replace('-', '')
            )

            # Confirm location (1 line instead of 8!)
            workflows.confirm_location(selectors.location, dest_loc)

        return success
