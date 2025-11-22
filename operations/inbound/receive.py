# operations/inbound/receive.py (simplified)
from core.logger import rf_log
from core.detour import ensure_detour_page_ready
from operations.base_operation import BaseOperation
from operations.inbound.receive_state_machine import ReceiveStateMachine
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

    def _fill_ilpn_quick_filter(self, ilpn: str, page=None) -> bool:
        """Fill the iLPN quick filter using the shared debug helper logic."""
        page = page or self.page
        try:
            from scripts.debug_ilpn_filter import _fill_ilpn_filter as debug_fill_ilpn
        except Exception as exc:
            rf_log(f"❌ iLPN debug helper unavailable: {exc}")
            return False

        try:
            return bool(debug_fill_ilpn(page, ilpn))
        except Exception as exc:
            rf_log(f"❌ iLPN filter via helper failed: {exc}")
            return False

    def _maybe_run_open_ui(self, open_ui_cfg: dict[str, Any] | list[dict[str, Any]] | None) -> bool:
        """Open one or more configured UIs mid-flow (e.g., Tasks or iLPNs)."""
        if not open_ui_cfg:
            return True

        # Normalize to a list of entries
        entries: list[dict[str, Any]] = []
        base_cfg: dict[str, Any] = {}
        if isinstance(open_ui_cfg, list):
            entries = open_ui_cfg
        elif isinstance(open_ui_cfg, dict):
            if not bool(open_ui_cfg.get("enabled", True)):
                return True
            base_cfg = open_ui_cfg
            entries = open_ui_cfg.get("entries") or [open_ui_cfg]
        else:
            return True

        nav_mgr_main = NavigationManager(self.page, self.screenshot_mgr)
        detour_nav = self.detour_nav or (NavigationManager(self.detour_page, self.screenshot_mgr) if self.detour_page else None)

        for idx, entry in enumerate(entries, 1):
            if not entry or not bool(entry.get("enabled", True)):
                continue

            use_nav = detour_nav if detour_nav else nav_mgr_main
            use_page = self.detour_page if self.detour_page else self.page

            if self.detour_page:
                ensure_detour_page_ready(self.detour_page, self.page, self.settings, self.screenshot_mgr)
                use_nav.close_active_windows(skip_titles=["rf menu"])

            search_term = entry.get("search_term") or base_cfg.get("search_term", "tasks")
            match_text = entry.get("match_text") or base_cfg.get("match_text", "Tasks (Configuration)")
            if not use_nav.open_menu_item(search_term, match_text, close_existing=True, onDemand=False):
                rf_log(f"❌ UI detour #{idx} failed during receive flow.")
                return False

            # Expand the detour window for better visibility/capture.
            try:
                use_page.wait_for_timeout(5000)
                use_nav.maximize_non_rf_windows()
            except Exception:
                pass

            operation_note = (
                entry.get("operation_note")
                or base_cfg.get("operation_note")
                or f"Visited UI #{idx} during receive"
            )
            screenshot_tag = (
                entry.get("screenshot_tag")
                or base_cfg.get("screenshot_tag")
                or f"receive_open_ui_{idx}"
            )

            rf_log(f"ℹ️ {operation_note}")

            if entry.get("close_after_open"):
                try:
                    windows = use_page.locator("div.x-window:visible")
                    if windows.count() > 0:
                        win = windows.last
                        try:
                            win.locator(".x-tool-close").first.click()
                        except Exception:
                            try:
                                use_page.keyboard.press("Escape")
                            except Exception:
                                pass
                    NavigationManager(use_page, self.screenshot_mgr).close_active_windows(skip_titles=[])
                except Exception:
                    pass

            if entry.get("fill_ilpn") and self._screen_context and self._screen_context.get("ilpn"):
                ilpn_val = self._screen_context.get("ilpn")
                if not self._fill_ilpn_quick_filter(str(ilpn_val), page=use_page):
                    return False
                use_page.wait_for_timeout(5000)
                self.screenshot_mgr.capture(use_page, screenshot_tag, operation_note)
        return True

    def _handle_open_ui(self, cfg: dict):
        self._maybe_run_open_ui(cfg)

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
        self._cache_screen_context()
        self._handle_open_ui(cfg)

    def _on_suggested_location(self, cfg: dict | None):
        """Hook invoked once suggested location is read."""
        if not cfg:
            return
        self._cache_screen_context()
        self._handle_open_ui(cfg)
