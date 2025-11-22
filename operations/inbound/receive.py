# operations/inbound/receive.py (simplified)

from operations.base_operation import BaseOperation
from operations.inbound.receive_state_machine import ReceiveStateMachine, ReceiveState
from operations.rf_primitives import RFMenuIntegration
from config.operations_config import OperationConfig


class ReceiveOperation(BaseOperation):
    """Handles ASN receiving workflow using state machine."""

    def __init__(self, page, page_mgr, screenshot_mgr, rf_menu, detour_page=None, settings=None):
        super().__init__(page, page_mgr, screenshot_mgr, rf_menu)
        
        integration = RFMenuIntegration(rf_menu)
        self.rf = integration.get_primitives()
        self.workflows = integration.get_workflows()
        self.selectors = OperationConfig.RECEIVE_SELECTORS
        self.detour_page = detour_page
        self.settings = settings
        
        # State machine handles all flow logic
        self.state_machine = ReceiveStateMachine(
            rf=self.workflows,
            screenshot_mgr=screenshot_mgr,
            selectors=self.selectors,
        )

    def execute(
        self,
        asn: str,
        item: str,
        quantity: int,
        *,
        flow_hint: str | None = None,
        auto_handle: bool = False,
        open_ui_cfg: dict | None = None,
    ) -> bool:
        """Execute receive operation via state machine."""
        
        success = self.state_machine.run(
            asn=asn,
            item=item,
            quantity=quantity,
            flow_hint=flow_hint,
            auto_handle=auto_handle,
        )
        
        # Handle post-receive UI detours if configured
        if success and open_ui_cfg:
            self._handle_open_ui(open_ui_cfg)
        
        return success
    
    def _handle_open_ui(self, cfg: dict):
        """Handle post-receive UI navigation (Tasks, iLPNs, etc.)"""
        # Keep your existing _maybe_run_open_ui logic here
        pass