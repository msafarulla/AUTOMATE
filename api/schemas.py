from pydantic import BaseModel
from typing import Optional

class ReceiveRequest(BaseModel):
    asn: str
    item: str
    quantity: int
    warehouse: Optional[str] = "LPM"

class OperationResponse(BaseModel):
    success: bool
    message: str
    screenshot_path: Optional[str] = None