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
        # Navigate to receive screen (2 lines instead of 6!)
        workflows.navigate_to_screen([
            ("2", "Outbound"),
            ("1", "Load Trailer")
        ])

        scans = [
            ("input#barcode20", shipment, "Shipment Id"),
            ("input#barcode13", dockDoor, "Dock Door"),
            ("input#barcode32", BOL, "BOL")
        ]

        # Fill all fields before submitting once
        for selector, value, label in scans:
            has_error, msg = workflows.scan_barcode(selector, value, label)
            if has_error:
                print(f"❌ {label} entry failed: {msg}")
                return False

        has_error, msg = workflows.press_enter("load_trailer")
        if has_error:
            print(f"❌ Submission failed: {msg}")
            return False


        return True
