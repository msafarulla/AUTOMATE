# operations/inbound/receive.py (simplified)
from core.logger import rf_log
from core.detour import run_open_ui_detours
from operations.base_operation import BaseOperation
from operations.inbound.receive_state_machine import ReceiveStateMachine
from operations.inbound.ilpn_filter_helper import fill_ilpn_filter
from operations.rf_primitives import RFMenuIntegration
from config.operations_config import OperationConfig
from typing import Any
from ui.navigation import NavigationManager
from utils.wait_utils import WaitUtils


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
        post_qty_hook = (lambda machine: self._on_qty_entered(open_ui_cfg)) if open_ui_cfg else None
        post_location_hook = (lambda machine: self._on_suggested_location(open_ui_cfg)) if open_ui_cfg else None

        success = self.state_machine.run(
            asn=asn,
            item=item,
            quantity=quantity,
            flow_hint=flow_hint,
            auto_handle=auto_handle,
            post_qty_hook=post_qty_hook,
            post_location_hook=post_location_hook,
        )
        self._cache_screen_context()
        return success

    def _fill_ilpn_quick_filter(self, ilpn: str, page=None, **kwargs: Any) -> bool:
        """Fill the iLPN quick filter using the debug helper logic (shared)."""
        page = page or self.page
        try:
            return bool(fill_ilpn_filter(page, ilpn, screenshot_mgr=self.screenshot_mgr, **kwargs))
        except Exception as exc:
            rf_log(f"❌ iLPN filter via helper failed: {exc}")
            return False

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

    def _on_qty_entered(self, cfg: dict | None):
        """Hook invoked immediately after quantity entry to run configured detours."""
        if not cfg:
            return
        WaitUtils.wait_brief(self.page)
        self._cache_screen_context()
        self._handle_open_ui(cfg)

    def _on_suggested_location(self, cfg: dict | None):
        """Hook invoked once suggested location is read."""
        if not cfg:
            return
        self._cache_screen_context()
        self._handle_open_ui(cfg)

    def _handle_open_ui(self, cfg: dict | list[dict] | None):
        """Invoke shared detour runner."""
        self._ensure_detour_nav()
        return run_open_ui_detours(
            cfg,
            main_page=self.page,
            screenshot_mgr=self.screenshot_mgr,
            main_nav=NavigationManager(self.page, self.screenshot_mgr),
            detour_page=self.detour_page,
            detour_nav=self.detour_nav,
            settings=self.settings,
            fill_ilpn_cb=self._fill_ilpn_quick_filter,
            screen_context=self._screen_context,
        )

    def _ensure_detour_nav(self):
        """Lazily create a detour page/nav only when detours are requested."""
        if self.detour_nav and self.detour_page:
            return
        try:
            new_page = self.page.context.new_page()
        except Exception:
            self.detour_page = None
            self.detour_nav = None
            return
        self.detour_page = new_page
        self.detour_nav = NavigationManager(new_page, self.screenshot_mgr)
