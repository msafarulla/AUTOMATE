from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration


class LoadingOperation(BaseOperation):
    """
    Refactored receive operation using reusable primitives.

    Compare this to the old receive.py - notice how much shorter and clearer it is!
    """

    def execute(self, shipment: str, dockDoor: str, quantity: int):

        # Create integration layer to get primitives and workflows
        integration = RFMenuIntegration(self.rf_menu)
        workflows = integration.get_workflows()
        rf = integration.get_primitives()

        # Navigate to receive screen (2 lines instead of 6!)
        workflows.navigate_to_screen([
            ("2", "Outbound"),
            ("1", "Load Trailer")
        ])

        # Scan Shipment
        has_error, msg = workflows.scan_barcode("input#barcode20", shipment, "Shipment Id")
        if has_error:
            print(f"❌ Shipment scan failed: {msg}")
            return False

        # Scan Dock Door
        has_error, msg = workflows.scan_barcode("input#barcode13", dockDoor, "Dock Door")
        if has_error:
            print(f"❌ Dock Door scan failed: {msg}")
            return False


        if 1==1:
            # Read suggested location (1 line instead of 5!)
            dest_loc = rf.read_field(
                "span#dataForm\\:SBRUdtltxt1_b1",
                transform=lambda x: x.replace('-', '')
            )

            # Confirm location (1 line instead of 8!)
            workflows.confirm_location("input#dataForm\\:locn", dest_loc)

        return True

