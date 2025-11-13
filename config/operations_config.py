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

    LOADING_MENU = MenuConfig(
        name="Load Trailer",
        tran_id="1012334"
    )

    LOADING_SELECTORS = ScreenSelectors({
        'shipment': "input#barcode20",
        'dock_door': "input#barcode13",
        'bol': "input#barcode32",
    })

    COMMON_SELECTORS = ScreenSelectors({
        'input_visible': "input[type='text']:visible",
        'focused_input': ":focus",
        'body': "body",
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
                'record_index': 0,
            },
            'receive': {
                'asn': '23907432',
                'item': 'J105SXC200TR',
                'quantity': 1,
            },
            'loading': {
                'shipment': '23907432',
                'dock_door': 'J105SXC200TR',
                'bol': 'MOH',
            }
        }
    ]


RECEIVE = OperationConfig.RECEIVE_MENU
LOADING = OperationConfig.LOADING_MENU
