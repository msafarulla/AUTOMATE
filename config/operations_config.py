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
        name="RDC: Recv - ASN",
        tran_id="1012408"
    )

    RECEIVE_SELECTORS = ScreenSelectors({
        'asn': "input#shipinpId",
        'item': "input#verfiyItemBrcd",
        'quantity': "input#input1input2",
        'location': "input#dataForm\\:locn",
        'suggested_location_aloc': "span#dataForm\\:SBRUdtltxt1_b1",
        'suggested_location_cloc': "span#dataForm\\:SBRUdtltxt1_b2",
    })

    RECEIVE_DEVIATION_SELECTORS = ScreenSelectors({
        'lpn_input': "input#lpninput",
        'lpn_input_name': "input[name='lpninput']",
    })

    # Metadata for receive flows that may branch off the happy path.
    RECEIVE_FLOW_METADATA = {
        'HAPPY_PATH': {
            'description': 'Standard location confirmation screen after quantity entry',
            'keywords': ['aloc'],
        },
        'IB_RULE_EXCEPTION_BLIND_ILPN': {
            'description': 'IB rule exception where iLPN prompt appears instead of suggested location',
            'keywords': ['blind ilpn', 'ilpn#'],
        },
        'QUANTITY_ADJUST': {
            'description': 'Quantity adjustment flow, typically recoverable',
            'keywords': ['qty adjust', 'quantity adjust'],
        },
        'UNKNOWN': {
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

    DEFAULT_WORKFLOWS = {
        'UI_Navigation': {
            'tasksUI': {
                    'Tasks': {
                    'enabled': True,
                },
        }
        }
    }

    # DEFAULT_WORKFLOWS = {
    #     'UI_Navigation': {
    #         'tasksUI': {
    #                 'Tasks': {
    #                 'enabled': True,
    #             },
    #     }
    #     },
    #     'inbound': {
    #         'receive_HAPPY_PATH': {
    #             'post': {
    #                 'enabled': True,
    #                 'source': 'db',
    #                 'type': 'ASN',
    #                 'message': None,  # manually an xml can be put here
    #                 'lookback_days': 14,
    #                 'db_env': 'prod',
    #                 'asn_items': [
    #                     {
    #                         'ItemName': '81402XC01C',
    #                         'Quantity': {'ShippedQty': 20000},
    #                     },
    #                 ],
    #             },
    #             'receive': {
    #                 'asn': '',
    #                 'item': '',
    #                 'quantity': 0,
    #                 'flow': 'HAPPY_PATH',
    #                 'auto_handle_deviation': True,
    #             },
    #         },
    #     },
    # }


RECEIVE = OperationConfig.RECEIVE_MENU
LOADING = OperationConfig.LOADING_MENU
