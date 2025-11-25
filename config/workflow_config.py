"""
Workflow Configuration System

Provides a cleaner, type-safe way to define automation workflows.
Replaces the deeply nested dict structure in operations_config.py.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from config.settings import StepNames


class FlowType(Enum):
    """Known receive flow variants."""
    HAPPY_PATH = "HAPPY_PATH"
    BLIND_ILPN = "IB_RULE_EXCEPTION_BLIND_ILPN"
    QUANTITY_ADJUST = "QUANTITY_ADJUST"
    UNKNOWN = "UNKNOWN"


@dataclass
class ASNItem:
    """Single item in an ASN."""
    item_name: str
    shipped_qty: int = 2000
    received_qty: int = 0
    qty_uom: str = "Unit"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ItemName": self.item_name,
            "Quantity": {
                "ShippedQty": self.shipped_qty,
                "ReceivedQty": self.received_qty,
                "QtyUOM": self.qty_uom,
            }
        }


@dataclass
class OpenTasksUiStep:
    """Tasks UI stage configuration."""
    search_term: str = "tasks"
    match_text: str = "Tasks (Configuration)"
    drill_detail: bool = False
    tab_click_timeout_ms: int = 3000
    operation_note: str | None = None
    screenshot_tag: str | None = None
    fill_ilpn: bool = False
    close_after_open: bool = False
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "search_term": self.search_term,
            "match_text": self.match_text,
            "drill_detail": self.drill_detail,
            "tab_click_timeout_ms": self.tab_click_timeout_ms,
            "operation_note": self.operation_note,
            "screenshot_tag": self.screenshot_tag,
            "fill_ilpn": self.fill_ilpn,
            "close_after_open": self.close_after_open,
        }


@dataclass
class OpenIlpnUiStep:
    """iLPNs UI stage configuration."""
    search_term: str = "ILPNS"
    match_text: str = "iLPNs (Distribution)"
    operation_note: str | None = "verify iLPN from the UI"
    screenshot_tag: str | None = None
    fill_ilpn: bool = True
    close_after_open: bool = False
    drill_detail: bool = False
    tab_click_timeout_ms: int = 3000
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "search_term": self.search_term,
            "match_text": self.match_text,
            "operation_note": self.operation_note,
            "screenshot_tag": self.screenshot_tag,
            "fill_ilpn": self.fill_ilpn,
            "close_after_open": self.close_after_open,
            "drill_detail": self.drill_detail,
            "tab_click_timeout_ms": self.tab_click_timeout_ms,
        }


@dataclass
class OpenUIConfig:
    """Configuration for UI detours during operations."""
    entries: list[OpenTasksUiStep | OpenIlpnUiStep] = field(default_factory=list)
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        if not self.enabled or not self.entries:
            return {}
        return {
            "enabled": self.enabled,
            "entries": [entry.to_dict() for entry in self.entries if entry],
        }


@dataclass
class PostMessageStep:
    """Post message stage configuration."""
    message_type: str  # "ASN" or "DistributionOrder"
    source: str = "db"
    db_env: str | None = None
    lookback_days: int = 14
    message: str | None = None  # Manual XML override
    asn_items: list[ASNItem] = field(default_factory=list)
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "source": self.source,
            "type": self.message_type,
            "db_env": self.db_env,
            "lookback_days": self.lookback_days,
            "message": self.message,
            "asn_items": [item.to_dict() for item in self.asn_items],
        }


@dataclass
class ReceivingStep:
    """Receive operation stage configuration."""
    asn: str = ""  # Often populated from post stage metadata
    item: str = ""
    quantity: int = 0
    flow: FlowType = FlowType.HAPPY_PATH
    auto_handle_deviation: bool = True
    open_ui: OpenUIConfig | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "asn": self.asn,
            "item": self.item,
            "quantity": self.quantity,
            "flow": self.flow.value,
            "auto_handle_deviation": self.auto_handle_deviation,
        }
        if self.open_ui:
            open_ui_cfg = self.open_ui.to_dict()
            if open_ui_cfg:
                result["open_ui"] = open_ui_cfg
        return result


@dataclass
class LoadingStep:
    """Loading operation stage configuration."""
    shipment: str
    dock_door: str
    bol: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "shipment": self.shipment,
            "dock_door": self.dock_door,
            "bol": self.bol,
        }


@dataclass
class Workflow:
    """Complete workflow definition."""
    name: str
    bucket: str = "inbound"
    steps: dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        return f"{self.bucket}.{self.name}"

    def to_tuple(self) -> tuple[str, dict[str, Any]]:
        """Convert to the format expected by WorkflowStageExecutor."""
        return (self.full_name, self.steps)


class WorkflowBuilder:
    """Fluent builder for creating workflows."""

    def __init__(self, name: str, bucket: str = "inbound", step_names: StepNames | None = None):
        self._name = name
        self._bucket = bucket
        self._steps: dict[str, Any] = {}
        self._step_names = step_names or StepNames()

    def postMessageStep(self, stage: PostMessageStep) -> "WorkflowBuilder":
        """Add a post message stage."""
        self._steps[self._step_names.postMessage] = stage.to_dict()
        return self

    def receivingStep(self, stage: ReceivingStep) -> "WorkflowBuilder":
        """Add a receive stage."""
        self._steps[self._step_names.runReceiving] = stage.to_dict()
        return self

    def loadingStep(self, stage: LoadingStep) -> "WorkflowBuilder":
        """Add a loading stage."""
        self._steps[self._step_names.runLoading] = stage.to_dict()
        return self

    def openTasksUiStep(self, stage: OpenTasksUiStep) -> "WorkflowBuilder":
        """Add a tasks UI stage."""
        self._steps[self._step_names.OpenTasksUi] = stage.to_dict()
        return self

    def openIlpnUiStep(self, stage: OpenIlpnUiStep) -> "WorkflowBuilder":
        """Add an iLPNs UI stage."""
        self._steps[self._step_names.OpenIlpnUi] = stage.to_dict()
        return self

    def build(self) -> Workflow:
        """Build the workflow."""
        return Workflow(
            name=self._name,
            bucket=self._bucket,
            steps=self._steps,
        )


# =============================================================================
# EXAMPLE WORKFLOWS
# =============================================================================

def create_default_workflows() -> list[Workflow]:
    """Create the default workflow configurations."""
    workflows = []

    # Standard receive happy path
    receive_happy = (
        WorkflowBuilder("receive_HAPPY_PATH", "inbound")
        .postMessageStep(PostMessageStep(
            message_type="ASN",
            source="db",
            lookback_days=14,
            db_env="prod",
            asn_items=[
                ASNItem(item_name="81402XC01C", shipped_qty=20000),
            ],
        ))
        .receivingStep(ReceivingStep(
            flow=FlowType.HAPPY_PATH,
            auto_handle_deviation=True,
            open_ui=OpenUIConfig(entries=[
                OpenIlpnUiStep(drill_detail=True),
            ]),
        ))
        .build()
    )
    workflows.append(receive_happy)

    return workflows


def workflows_to_legacy_format(workflows: list[Workflow]) -> dict[str, dict[str, dict]]:
    """
    Convert workflow list to legacy nested dict format.
    
    This allows gradual migration - new code can use WorkflowBuilder,
    while existing code continues to work with the dict format.
    """
    result: dict[str, dict[str, dict]] = {}
    
    for workflow in workflows:
        if workflow.bucket not in result:
            result[workflow.bucket] = {}
        result[workflow.bucket][workflow.name] = workflow.steps
    
    return result


def flatten_workflows(workflows: list[Workflow]) -> list[tuple[str, dict[str, Any]]]:
    """
    Flatten workflows to list of (name, stages) tuples.
    
    This is the format expected by main.py's run_automation().
    """
    return [workflow.to_tuple() for workflow in workflows]
