"""
Loading Operation - Outbound Processing
Handles shipment loading, dock door assignment, and BOL generation
"""
from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration
from core.logger import rf_log


class LoadingOperation(BaseOperation):
    """
    Process outbound shipments through RF terminal.
    
    Workflow:
    1. Navigate to Load Trailer screen
    2. Scan shipment ID
    3. Assign dock door
    4. Generate/confirm BOL (Bill of Lading)
    """
    
    # Menu navigation constants
    MENU_NAME = "Load Trailer"
    TRAN_ID = "1012334"
    
    # Screen selectors
    SELECTOR_SHIPMENT = "input#barcode20"
    SELECTOR_DOCK_DOOR = "input#barcode13"
    SELECTOR_BOL = "input#barcode32"

    def execute(self, shipment: str, dock_door: str, bol: str) -> bool:
        """
        Execute loading operation.
        
        Args:
            shipment: Shipment ID to load
            dock_door: Dock door assignment
            bol: Bill of Lading number
            
        Returns:
            True if operation successful, False otherwise
        """
        # Initialize RF integration
        integration = RFMenuIntegration(self.rf_menu)
        workflows = integration.get_workflows()
        
        # Step 1: Navigate to loading screen
        rf_log(f"🚚 Starting loading: Shipment={shipment}, Door={dock_door}, BOL={bol}")
        
        if not workflows.navigate_to_menu_by_search(self.MENU_NAME, self.TRAN_ID):
            rf_log("❌ Failed to navigate to loading screen")
            return False
        
        # Step 2: Scan all required fields and submit
        scans = [
            (self.SELECTOR_SHIPMENT, shipment, "Shipment ID"),
            (self.SELECTOR_DOCK_DOOR, dock_door, "Dock Door"),
            (self.SELECTOR_BOL, bol, "BOL")
        ]
        
        has_error, msg = workflows.scan_fields_and_submit(scans, "load_trailer")
        
        if has_error:
            rf_log(f"❌ Loading failed: {msg}")
            return False
        
        rf_log(f"✅ Loading completed: Shipment={shipment}, Door={dock_door}, BOL={bol}")
        return True