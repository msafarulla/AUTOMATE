from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration
from config.operations_config import OperationConfig


class LoadingOperation(BaseOperation):
    """
    Refactored receive operation using reusable primitives.

    Compare this to the old receive.py - notice how much shorter and clearer it is!
    """

    def execute(self, shipment: str, dockDoor: str, BOL: str):

        menu_cfg = OperationConfig.LOADING_MENU
        selectors = OperationConfig.LOADING_SELECTORS

        # Create integration layer to get primitives and workflows
        integration = RFMenuIntegration(self.rf_menu)
        workflows = integration.get_workflows()

        search_term = menu_cfg.search_term or menu_cfg.name
        if not workflows.navigate_to_menu_by_search(search_term, menu_cfg.tran_id):
            return False

        scans = [
            (selectors.shipment, shipment, "Shipment Id"),
            (selectors.dock_door, dockDoor, "Dock Door"),
            (selectors.bol, BOL, "BOL")
        ]

        has_error, msg = workflows.scan_fields_and_submit(scans, "load_trailer")
        if has_error:
            return False
        return True
