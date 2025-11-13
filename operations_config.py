"""
Configuration and constants for warehouse operations.
Centralizes all selectors, menu names, and transaction IDs.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class MenuConfig:
    """Configuration for RF menu navigation"""
    name: str
    tran_id: str
    search_term: str = None
    
    def __post_init__(self):
        if self.search_term is None:
            self.search_term = self.name


@dataclass
class ScreenSelectors:
    """Selectors for a specific RF screen"""
    selectors: Dict[str, str]
    
    def __getattr__(self, name: str) -> str:
        """Allow dot notation access to selectors"""
        if name in self.selectors:
            return self.selectors[name]
        raise AttributeError(f"No selector found for: {name}")


class OperationConfig:
    """
    Centralized configuration for all warehouse operations.
    Makes it easy to update selectors when the UI changes.
    """
    
    # ========================================================================
    # RECEIVE OPERATION
    # ========================================================================
    
    RECEIVE_MENU = MenuConfig(
        name="RDC: Recv",
        tran_id="1012408"
    )
    
    RECEIVE_SELECTORS = ScreenSelectors({
        'asn': "input#shipinpId",
        'item': "input#verfiyItemBrcd",
        'quantity': "input#input1input2",
        'location': "input#dataForm\\:locn",
        'suggested_location': "span#dataForm\\:SBRUdtltxt1_b1",
    })
    
    # ========================================================================
    # LOADING OPERATION
    # ========================================================================
    
    LOADING_MENU = MenuConfig(
        name="Load Trailer",
        tran_id="1012334"
    )
    
    LOADING_SELECTORS = ScreenSelectors({
        'shipment': "input#barcode20",
        'dock_door': "input#barcode13",
        'bol': "input#barcode32",
    })
    
    # ========================================================================
    # COMMON SELECTORS
    # ========================================================================
    
    COMMON_SELECTORS = ScreenSelectors({
        'input_visible': "input[type='text']:visible",
        'focused_input': ":focus",
        'body': "body",
    })
    
    # ========================================================================
    # KEYBOARD SHORTCUTS
    # ========================================================================
    
    KEYS = {
        'home': "Control+b",
        'search': "Control+f",
        'accept': "Control+a",
        'show_tran': "Control+p",
    }
    
    # ========================================================================
    # TIMEOUTS (milliseconds)
    # ========================================================================
    
    TIMEOUTS = {
        'default': 2000,
        'fast': 1000,
        'slow': 5000,
        'location_read': 3000,
    }
    
    # ========================================================================
    # VALIDATION PATTERNS
    # ========================================================================
    
    PATTERNS = {
        'asn': r'^\d{8}$',  # 8 digits
        'item': r'^[A-Z0-9]{10,}$',  # Alphanumeric, 10+ chars
        'location': r'^[A-Z0-9-]{4,}$',  # Location code
    }


# Convenience accessors
RECEIVE = OperationConfig.RECEIVE_MENU
LOADING = OperationConfig.LOADING_MENU