from dataclasses import dataclass
from typing import Optional

@dataclass
class ASN:
    asn_number: str
    warehouse: str
    items: list

@dataclass
class Item:
    item_id: str
    description: str
    quantity: int
    location: Optional[str] = None

@dataclass
class OperationResult:
    success: bool
    message: str
    data: Optional[dict] = None