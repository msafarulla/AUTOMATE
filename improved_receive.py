"""
Receive Operation - Inbound Processing
Handles ASN receiving, item verification, and put-away
"""
from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration
from core.logger import rf_log


class ReceiveOperation(BaseOperation):
    """
    Process inbound shipments through RF terminal.
    
    Workflow:
    1. Navigate to RDC: Recv screen
    2. Scan ASN (Advanced Shipment Notice)
    3. Verify item barcode
    4. Enter quantity
    5. Confirm put-away location
    """
    
    # Menu navigation constants
    MENU_NAME = "RDC: Recv"
    TRAN_ID = "1012408"
    
    # Screen selectors
    SELECTOR_ASN = "input#shipinpId"
    SELECTOR_ITEM = "input#verfiyItemBrcd"
    SELECTOR_QTY = "input#input1input2"
    SELECTOR_LOCATION = "input#dataForm\\:locn"
    SELECTOR_SUGGESTED_LOC = "span#dataForm\\:SBRUdtltxt1_b1"

    def execute(self, asn: str, item: str, quantity: int = 1) -> bool:
        """
        Execute receive operation.
        
        Args:
            asn: Advanced Shipment Notice ID
            item: Item barcode/SKU
            quantity: Number of units to receive (default: 1)
            
        Returns:
            True if operation successful, False otherwise
        """
        # Initialize RF integration
        integration = RFMenuIntegration(self.rf_menu)
        workflows = integration.get_workflows()
        rf = integration.get_primitives()
        
        # Step 1: Navigate to receive screen
        rf_log(f"📦 Starting receive: ASN={asn}, Item={item}, Qty={quantity}")
        
        if not workflows.navigate_to_menu_by_search(self.MENU_NAME, self.TRAN_ID):
            rf_log("❌ Failed to navigate to receive screen")
            return False
        
        # Step 2: Scan ASN
        has_error, msg = workflows.scan_barcode_auto_enter(
            self.SELECTOR_ASN, 
            asn, 
            "ASN"
        )
        if has_error:
            rf_log(f"❌ ASN scan failed: {msg}")
            return False
        
        # Step 3: Verify item
        has_error, msg = workflows.scan_barcode_auto_enter(
            self.SELECTOR_ITEM, 
            item, 
            "Item"
        )
        if has_error:
            rf_log(f"❌ Item verification failed: {msg}")
            return False
        
        # Step 4: Enter quantity
        if not workflows.enter_quantity(self.SELECTOR_QTY, quantity, item):
            rf_log("❌ Quantity entry failed")
            return False
        
        # Step 5: Confirm location
        try:
            # Read system-suggested location
            dest_loc = rf.read_field(
                self.SELECTOR_SUGGESTED_LOC,
                transform=lambda x: x.replace('-', '')  # Remove dashes
            )
            rf_log(f"📍 Suggested location: {dest_loc}")
            
            # Confirm the location
            has_error, msg = workflows.confirm_location(
                self.SELECTOR_LOCATION, 
                dest_loc
            )
            
            if has_error:
                rf_log(f"❌ Location confirmation failed: {msg}")
                return False
                
        except Exception as e:
            rf_log(f"❌ Error during location handling: {e}")
            return False
        
        rf_log(f"✅ Receive completed: ASN={asn}, Item={item}, Qty={quantity}, Loc={dest_loc}")
        return True