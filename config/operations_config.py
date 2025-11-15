"""
Configuration and constants for warehouse operations.
Centralizes selectors, menu names, and transaction IDs.
"""
from dataclasses import dataclass
from typing import Dict


@dataclass
class MenuConfig:
    """Configuration for RF menu navigation."""
    name: str
    tran_id: str
    search_term: str | None = None

    def __post_init__(self):
        if self.search_term is None:
            self.search_term = self.name


@dataclass
class ScreenSelectors:
    """Selectors for a specific RF screen."""
    selectors: Dict[str, str]

    def __getattr__(self, name: str) -> str:
        if name in self.selectors:
            return self.selectors[name]
        raise AttributeError(f"No selector found for: {name}")


class OperationConfig:
    """Centralized configuration for warehouse operations."""

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

    # Metadata for receive flows that may branch off the happy path.
    RECEIVE_FLOW_METADATA = {
        'HAPPY_PATH': {
            'auto_handle': True,
            'description': 'Standard location confirmation screen after quantity entry',
            'body_keywords': ['aloc'],
            'requires_suggested': True,
        },
        'HOLD_REASON': {
            'auto_handle': False,
            'description': 'Hold reason prompt that requires manual judgment',
            'body_keywords': ['hold reason'],
        },
        'QUANTITY_ADJUST': {
            'auto_handle': True,
            'description': 'Quantity adjustment flow, typically recoverable',
            'body_keywords': ['qty adjust', 'quantity adjust'],
        },
        'UNKNOWN': {
            'auto_handle': False,
            'description': 'Unknown/uncategorized screen – treat as deviation',
        },
    }

    LOADING_MENU = MenuConfig(
        name="Load Trailer",
        tran_id="1012334"
    )

    LOADING_SELECTORS = ScreenSelectors({
        'shipment': "input#barcode20",
        'dock_door': "input#barcode13",
        'bol': "input#barcode32",
    })

    KEYS = {
        'home': "Control+b",
        'search': "Control+f",
        'accept': "Control+a",
        'show_tran': "Control+p",
    }

    TIMEOUTS = {
        'default': 2000,
        'fast': 1000,
        'slow': 5000,
        'location_read': 3000,
    }

    PATTERNS = {
        'asn': r'^\d{8}$',
        'item': r'^[A-Z0-9]{10,}$',
        'location': r'^[A-Z0-9-]{4,}$',
    }

    DEFAULT_WORKFLOWS = [
        {
            'post': {
                'enabled': True,
                'source': 'db',
                'type': 'ASN',
                'message': None, #manually an xml can be put here
                'lookback_days': 14,
                'db_env': 'prod',
                 'asn_items': [
                     {
                         'ItemName': '81402XC01C',
                         'PurchaseOrderID': 'M28R217',  # optional unless you need to override
                         'Quantity': {'ShippedQty': 2000},
                     },
                 ],
            },
            'receive': {
                'asn': '',
                'item': '',
                'quantity': 0,
                'flow': 'HAPPY_PATH',
            },
            'loading': {
                'shipment': '',
                'dock_door': '',
                'bol': '',
            }
        }
    ]


RECEIVE = OperationConfig.RECEIVE_MENU
LOADING = OperationConfig.LOADING_MENU
