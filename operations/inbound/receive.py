# operations/inbound/receive.py (simplified)
from core.logger import rf_log
from core.detour import DetourManager, NullDetourManager
from operations.base_operation import BaseOperation
from operations.inbound.receive_state_machine import ReceiveStateMachine
from operations.inbound.ilpn_filter_helper import fill_ilpn_filter
from operations.rf_primitives import RFMenuIntegration
from config.operations_config import OperationConfig
from typing import Any
from ui.navigation import NavigationManager


class ReceiveOperation(BaseOperation):
    """Handles ASN receiving workflow using state machine."""

    def __init__(self, page, page_mgr, screenshot_mgr, rf_menu, detour_page=None, detour_nav=None, settings=None):
        super().__init__(page, page_mgr, screenshot_mgr, rf_menu)

        integration = RFMenuIntegration(rf_menu)
        self.rf = integration.get_primitives()
        self.workflows = integration.get_workflows()
        self.selectors = OperationConfig.RECEIVE_SELECTORS
        self.detour_page = detour_page
        self.detour_nav = detour_nav or (NavigationManager(detour_page, screenshot_mgr) if detour_page else None)
        self.settings = settings
        self._screen_context: dict[str, int | None] | None = None
        self.detour_manager = NullDetourManager()
        
        # State machine handles all flow logic
        self.state_machine = ReceiveStateMachine(
            rf=self.workflows,
            screenshot_mgr=screenshot_mgr,
            selectors=self.selectors,
            detour_manager=self.detour_manager,
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
        # Wire detours for this run (state machine will invoke them).
        self.detour_manager = DetourManager(
            open_ui_cfg=open_ui_cfg,
            main_page=self.page,
            screenshot_mgr=self.screenshot_mgr,
            main_nav=NavigationManager(self.page, self.screenshot_mgr),
            detour_page=self.detour_page,
            detour_nav=self.detour_nav,
            settings=self.settings,
            fill_ilpn_cb=self._fill_ilpn_quick_filter,
        ) if open_ui_cfg else NullDetourManager()

        self.state_machine.detours = self.detour_manager

        success = self.state_machine.run(
            asn=asn,
            item=item,
            quantity=quantity,
            flow_hint=flow_hint,
            auto_handle=auto_handle,
            post_qty_hook=None,
            post_location_hook=None,
        )
        self._cache_screen_context()
        return success

    def _cache_screen_context(self):
        """Pull key values from the state machine for later detour use (i.e., iLPN fill)."""
        ctx = getattr(self.state_machine, "context", None)
        if not ctx:
            self._screen_context = None
            return

        self._screen_context = {
            "asn": ctx.asn,
            "item": ctx.item,
            "quantity": ctx.quantity,
            "shipped_qty": ctx.shipped_qty,
            "received_qty": ctx.received_qty,
            "ilpn": ctx.ilpn,
            "suggested_location": ctx.suggested_location,
            "flow_hint": ctx.flow_hint,
        }

    def _fill_ilpn_quick_filter(self, ilpn: str, page=None, **kwargs: Any) -> bool:
        """Fill the iLPN quick filter using the debug helper logic (shared)."""
        page = page or self.page
        try:
            return bool(fill_ilpn_filter(page, ilpn, screenshot_mgr=self.screenshot_mgr, **kwargs))
        except Exception as exc:
            rf_log(f"❌ iLPN filter via helper failed: {exc}")
            return False
