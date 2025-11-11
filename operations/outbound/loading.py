from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration


class LoadingOperation(BaseOperation):
    """
    Refactored receive operation using reusable primitives.

    Compare this to the old receive.py - notice how much shorter and clearer it is!
    """

    def execute(self, shipment: str, dockDoor: str, BOL: str):

        # Create integration layer to get primitives and workflows
        integration = RFMenuIntegration(self.rf_menu)
        workflows = integration.get_workflows()
        # Navigate to receive screen
        workflows.navigate_to_screen([
            ("2", "Outbound"),
            ("1", "Load Trailer")
        ])

        scans = [
            ("input#barcode20", shipment, "Shipment Id"),
            ("input#barcode13", dockDoor, "Dock Door"),
            ("input#barcode32", BOL, "BOL")
        ]

        has_error, msg = workflows.scan_fields_and_submit(scans, "load_trailer")
        if has_error:
            return False
        return True
