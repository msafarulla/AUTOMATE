# operations/inbound/receive_state_machine.py

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional
from datetime import datetime

from core.logger import rf_log
from core.screenshot import ScreenshotManager
from operations.rf_primitives import RFWorkflows
from config.operations_config import OperationConfig, ScreenSelectors
from utils.retry import retry_with_context


class ReceiveState(Enum):
    """All possible states in the receive flow."""
    INIT = auto()
    NAVIGATED = auto()
    ASN_SCANNED = auto()
    ITEM_SCANNED = auto()
    QTY_ENTERED = auto()
    
    # Post-quantity branches
    AWAITING_LOCATION = auto()
    AWAITING_BLIND_ILPN = auto()
    CANT_FIND_PUTAWAY_LOCATION = auto()
    
    # Terminal states
    COMPLETE = auto()
    ERROR = auto()
    ABORTED = auto()


@dataclass
class ReceiveContext:
    """Shared context passed through state transitions."""
    asn: str = ""
    item: str = ""
    quantity: int = 0
    
    # Screen data captured during flow
    shipped_qty: Optional[int] = None
    received_qty: Optional[int] = None
    ilpn: Optional[str] = None
    suggested_location: Optional[str] = None
    
    # Flow control
    flow_hint: Optional[str] = None
    auto_handle_deviation: bool = False
    
    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    
    # Audit trail
    transitions: list[tuple[ReceiveState, ReceiveState, str]] = field(default_factory=list)
    
    def record_transition(self, from_state: ReceiveState, to_state: ReceiveState, reason: str = ""):
        self.transitions.append((from_state, to_state, reason))


class StateHandler(ABC):
    """Base class for state-specific logic."""
    
    state: ReceiveState
    
    @abstractmethod
    def execute(self, machine: ReceiveStateMachine) -> ReceiveState:
        """Execute state logic and return next state."""
        pass
    
    @abstractmethod
    def detect(self, machine: ReceiveStateMachine) -> bool:
        """Return True if current screen matches this state."""
        pass


class ReceiveStateMachine:
    """
    State machine for ASN receiving workflow.
    
    Usage:
        machine = ReceiveStateMachine(rf_workflows, screenshot_mgr, selectors)
        success = machine.run(asn="12345678", item="PART123", quantity=100)
    """
    
    def __init__(
        self,
        rf: RFWorkflows,
        screenshot_mgr: ScreenshotManager,
        selectors: ScreenSelectors,
        deviation_selectors: Optional[ScreenSelectors] = None,
        post_qty_hook: Optional[Callable[['ReceiveStateMachine'], None]] = None,
        post_location_hook: Optional[Callable[['ReceiveStateMachine'], None]] = None,
    ):
        self.rf = rf
        self.screenshot_mgr = screenshot_mgr
        self.selectors = selectors
        self.deviation_selectors = deviation_selectors or OperationConfig.RECEIVE_DEVIATION_SELECTORS
        self.post_qty_hook = post_qty_hook
        self.post_location_hook = post_location_hook
        
        self.state = ReceiveState.INIT
        self.context = ReceiveContext()
        self.handlers: dict[ReceiveState, StateHandler] = {}
        self.detectors: list[StateHandler] = []
        self._post_qty_hook_called = False
        self._post_location_hook_called = False
        
        self._register_handlers()
    
    def _register_handlers(self):
        """Register all state handlers."""
        handlers = [
            InitHandler(),
            NavigatedHandler(),
            AsnScannedHandler(),
            ItemScannedHandler(),
            QtyEnteredHandler(),
            AwaitingLocationHandler(),
            AwaitingBlindIlpnHandler(),
            CantFindPutawayLocationHandler(),
            CompleteHandler(),
            ErrorHandler(),
        ]
        
        for handler in handlers:
            self.handlers[handler.state] = handler
            if hasattr(handler, 'detect'):
                self.detectors.append(handler)
    
    def run(
        self,
        asn: str,
        item: str,
        quantity: int,
        flow_hint: Optional[str] = None,
        auto_handle: bool = False,
        post_qty_hook: Optional[Callable[['ReceiveStateMachine'], None]] = None,
        post_location_hook: Optional[Callable[['ReceiveStateMachine'], None]] = None,
    ) -> bool:
        """
        Execute the complete receive flow.
        
        Returns True if receive completed successfully.
        """
        # Initialize context
        self.context = ReceiveContext(
            asn=asn,
            item=item,
            quantity=quantity,
            flow_hint=flow_hint,
            auto_handle_deviation=auto_handle,
        )
        self.state = ReceiveState.INIT
        self._post_qty_hook_called = False
        # Allow override of hooks per run (mainly for tests)
        if post_qty_hook is not None:
            self.post_qty_hook = post_qty_hook
        if post_location_hook is not None:
            self.post_location_hook = post_location_hook
        self._post_location_hook_called = False
        
        rf_log(f"🚀 Starting receive: ASN={asn}, Item={item}, Qty={quantity}")
        
        # Main state loop
        while not self._is_terminal():
            prev_state = self.state
            
            try:
                handler = self.handlers.get(self.state)
                if not handler:
                    rf_log(f"❌ No handler for state: {self.state}")
                    self._transition_to(ReceiveState.ERROR, "Missing handler")
                    break
                
                next_state = handler.execute(self)
                self._transition_to(next_state, f"Handler returned {next_state.name}")
                
            except Exception as e:
                rf_log(f"❌ Exception in {self.state.name}: {e}")
                self.context.error_message = str(e)
                self._transition_to(ReceiveState.ERROR, f"Exception: {e}")
        
        # Log result
        success = self.state == ReceiveState.COMPLETE
        self._log_summary(success)
        return success
    
    def detect_current_state(self) -> ReceiveState:
        """
        Detect current state from screen content.
        Used for recovery and deviation handling.
        """
        for detector in self.detectors:
            try:
                if detector.detect(self):
                    return detector.state
            except Exception:
                continue
        return ReceiveState.ERROR
    
    def read_screen_text(self) -> str:
        """Get current RF screen body text."""
        try:
            return self.rf.primitive.read_field("body").lower()
        except Exception:
            return ""
    
    def is_element_visible(self, selector: str, timeout: int = 500) -> bool:
        """Check if element is visible on current screen."""
        try:
            rf_iframe = self.rf.primitive.get_iframe()
            locator = rf_iframe.locator(selector)
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False
    
    def rf_capture(self, label: str, text: Optional[str] = None):
        """Capture RF screenshot with current state context."""
        overlay = text or f"{self.state.name}: {self.context.item}"
        self.screenshot_mgr.capture_rf_window(
            self.rf.primitive.page,
            f"{self.state.name.lower()}_{label}",
            overlay
        )
    
    def invoke_post_qty_hook(self):
        """Run optional post-quantity hook exactly once."""
        if not self.post_qty_hook or self._post_qty_hook_called:
            return
        try:
            self.post_qty_hook(self)
        except Exception as exc:
            rf_log(f"⚠️ post_qty_hook failed: {exc}")
        self._post_qty_hook_called = True

    def invoke_post_location_hook(self):
        """Run optional post-location hook exactly once."""
        if not self.post_location_hook or self._post_location_hook_called:
            return
        try:
            self.post_location_hook(self)
        except Exception as exc:
            rf_log(f"⚠️ post_location_hook failed: {exc}")
        self._post_location_hook_called = True
    
    def _transition_to(self, new_state: ReceiveState, reason: str = ""):
        """Record state transition."""
        if new_state != self.state:
            self.context.record_transition(self.state, new_state, reason)
            rf_log(f"  {self.state.name} → {new_state.name}" + (f" ({reason})" if reason else ""))
            self.state = new_state
    
    def _is_terminal(self) -> bool:
        """Check if current state is terminal."""
        return self.state in (
            ReceiveState.COMPLETE,
            ReceiveState.ERROR,
            ReceiveState.ABORTED,
        )
    
    def _log_summary(self, success: bool):
        """Log flow summary."""
        icon = "✅" if success else "❌"
        rf_log(f"{icon} Receive {'completed' if success else 'failed'}: {self.context.asn}")
        rf_log(f"   Transitions: {len(self.context.transitions)}")
        if self.context.error_message:
            rf_log(f"   Error: {self.context.error_message}")


# =============================================================================
# STATE HANDLERS
# =============================================================================

class InitHandler(StateHandler):
    state = ReceiveState.INIT
    
    def execute(self, machine: ReceiveStateMachine) -> ReceiveState:
        menu = OperationConfig.RECEIVE_MENU
        search_term = menu.search_term or menu.name
        if machine.rf.navigate_to_menu_by_search(search_term, menu.tran_id):
            return ReceiveState.NAVIGATED
        return ReceiveState.ERROR
    
    def detect(self, machine: ReceiveStateMachine) -> bool:
        # Init is not detectable from screen
        return False


class NavigatedHandler(StateHandler):
    state = ReceiveState.NAVIGATED
    
    def execute(self, machine: ReceiveStateMachine) -> ReceiveState:
        has_error, msg = machine.rf.scan_barcode_auto_enter(
            machine.selectors.asn,
            machine.context.asn,
            "ASN"
        )
        if has_error:
            machine.context.error_message = msg
            return ReceiveState.ERROR
        return ReceiveState.ASN_SCANNED
    
    def detect(self, machine: ReceiveStateMachine) -> bool:
        return machine.is_element_visible(machine.selectors.asn)


class AsnScannedHandler(StateHandler):
    state = ReceiveState.ASN_SCANNED
    
    def execute(self, machine: ReceiveStateMachine) -> ReceiveState:
        has_error, msg = machine.rf.scan_barcode_auto_enter(
            machine.selectors.item,
            machine.context.item,
            "Item"
        )
        if has_error:
            machine.context.error_message = msg
            return ReceiveState.ERROR
        
        # Capture screen quantities after item scan
        machine.context.shipped_qty, machine.context.received_qty, machine.context.ilpn = (
            _parse_screen_quantities(machine)
        )
        
        return ReceiveState.ITEM_SCANNED
    
    def detect(self, machine: ReceiveStateMachine) -> bool:
        return machine.is_element_visible(machine.selectors.item)


class ItemScannedHandler(StateHandler):
    state = ReceiveState.ITEM_SCANNED
    
    def execute(self, machine: ReceiveStateMachine) -> ReceiveState:
        context_dict = {
            "shipped": machine.context.shipped_qty,
            "received": machine.context.received_qty,
            "ilpn": machine.context.ilpn,
        }
        
        success = machine.rf.enter_quantity(
            machine.selectors.quantity,
            machine.context.quantity,
            item_name=machine.context.item,
            context=context_dict,
        )
        
        if not success:
            machine.context.error_message = "Quantity entry failed"
            return ReceiveState.ERROR
        
        return ReceiveState.QTY_ENTERED
    
    def detect(self, machine: ReceiveStateMachine) -> bool:
        return machine.is_element_visible(machine.selectors.quantity)


class QtyEnteredHandler(StateHandler):
    """
    Critical branching point after quantity entry.
    Detects which sub-flow we're in and routes accordingly.
    """
    state = ReceiveState.QTY_ENTERED
    
    BRANCH_DETECTORS = [
        # (next_state, detection_method)
        (ReceiveState.AWAITING_LOCATION, '_is_location_prompt'),
        (ReceiveState.AWAITING_BLIND_ILPN, '_is_blind_ilpn_prompt'),
        (ReceiveState.CANT_FIND_PUTAWAY_LOCATION, '_r_stage_prompt'),
    ]
    
    def execute(self, machine: ReceiveStateMachine) -> ReceiveState:
        machine.invoke_post_qty_hook()
        screen_text = machine.read_screen_text()
        
        for next_state, detector_name in self.BRANCH_DETECTORS:
            detector = getattr(self, detector_name)
            if detector(machine, screen_text):
                # Check if this matches expected flow
                if machine.context.flow_hint:
                    expected = self._state_to_flow_name(next_state)
                    if expected != machine.context.flow_hint:
                        rf_log(f"⚠️ Flow deviation: expected {machine.context.flow_hint}, got {expected}")
                        machine.rf_capture("deviation", f"Expected {machine.context.flow_hint}")
                        if not machine.context.auto_handle_deviation:
                            machine.context.error_message = f"Flow deviation: {expected}"
                            return ReceiveState.ERROR
                
                return next_state
        
        # Unknown screen state
        rf_log(f"⚠️ Unknown screen after qty entry: {screen_text[:100]}")
        machine.rf_capture("unknown_state", "Unknown screen")
        machine.context.error_message = "Unknown screen state after quantity"
        return ReceiveState.ERROR
    
    def detect(self, machine: ReceiveStateMachine) -> bool:
        # QTY_ENTERED is transitional, not directly detectable
        return False
    
    def _is_location_prompt(self, machine: ReceiveStateMachine, text: str) -> bool:
        # Check for location selector visibility
        if machine.is_element_visible(machine.selectors.location, timeout=300):
            return True
        # Fallback to text detection
        return any(marker in text for marker in ('aloc', 'cloc', 'location'))
    
    def _is_blind_ilpn_prompt(self, machine: ReceiveStateMachine, text: str) -> bool:
        if machine.is_element_visible(machine.deviation_selectors.lpn_input, timeout=300):
            return True
        return 'blind ilpn' in text or 'ilpn#' in text
    
    def _is_qty_adjust_prompt(self, machine: ReceiveStateMachine, text: str) -> bool:
        return 'qty adjust' in text or 'quantity adjust' in text

    def _r_stage_prompt(self, machine: ReceiveStateMachine, text: str) -> bool:
        try:
            if machine.is_element_visible(machine.deviation_selectors.rstage_location, timeout=300):
                return True
        except Exception:
            pass

        try:
            if machine.is_element_visible(machine.deviation_selectors.rstage_location_name, timeout=300):
                return True
        except Exception:
            pass

        return 'exception r-stage' in text.lower() or 'r-stage' in text.lower()
    
    def _state_to_flow_name(self, state: ReceiveState) -> str:
        mapping = {
            ReceiveState.AWAITING_LOCATION: "HAPPY_PATH",
            ReceiveState.AWAITING_BLIND_ILPN: "IB_RULE_EXCEPTION_BLIND_ILPN",
            ReceiveState.CANT_FIND_PUTAWAY_LOCATION: "CANT_FIND_LOCATION",
        }
        return mapping.get(state, "UNKNOWN")


class AwaitingLocationHandler(StateHandler):
    state = ReceiveState.AWAITING_LOCATION
    
    def execute(self, machine: ReceiveStateMachine) -> ReceiveState:
        location = _read_suggested_location(machine)
        machine.context.suggested_location = location
        
        if not location:
            machine.context.error_message = "Could not read suggested location"
            return ReceiveState.ERROR
        
        has_error, msg = machine.rf.confirm_location(machine.selectors.location, location)
        if has_error:
            machine.context.error_message = msg
            return ReceiveState.ERROR
        
        machine.invoke_post_location_hook()
        machine.rf_capture("complete", f"Location confirmed: {location}")
        return ReceiveState.COMPLETE
    
    def detect(self, machine: ReceiveStateMachine) -> bool:
        return machine.is_element_visible(machine.selectors.location)


class AwaitingBlindIlpnHandler(StateHandler):
    state = ReceiveState.AWAITING_BLIND_ILPN
    
    def execute(self, machine: ReceiveStateMachine) -> ReceiveState:
        lpn = datetime.now().strftime("%y%m%d%H%M%S")
        
        selectors_to_try = [
            machine.deviation_selectors.lpn_input,
            machine.deviation_selectors.lpn_input_name,
        ]
        
        for selector in selectors_to_try:
            try:
                has_error, msg = machine.rf.primitive.fill_and_submit(
                    selector, lpn, "blind_ilpn", f"Entered LPN: {lpn}"
                )
                if not has_error:
                    machine.rf_capture("ilpn_entered", f"Blind iLPN: {lpn}")
                    # After ILPN, usually goes to location
                    return ReceiveState.AWAITING_LOCATION
            except Exception:
                continue
        
        machine.context.error_message = "Could not enter blind iLPN"
        return ReceiveState.ERROR
    
    def detect(self, machine: ReceiveStateMachine) -> bool:
        text = machine.read_screen_text()
        return 'blind ilpn' in text or 'ilpn#' in text


class CantFindPutawayLocationHandler(StateHandler):
    state = ReceiveState.CANT_FIND_PUTAWAY_LOCATION
    
    def execute(self, machine: ReceiveStateMachine) -> ReceiveState:
        # Qty adjust usually requires accepting and continuing
        machine.rf.primitive.accept_message()
        machine.rf_capture("Cant find location", "Accepted the Warning")

        # Re-detect what screen we're on now
        return machine.detect_current_state()
    
    def detect(self, machine: ReceiveStateMachine) -> bool:
        text = machine.read_screen_text()
        return 'exception r-stage' in text.lower() or 'r-stage' in text.lower()


class CompleteHandler(StateHandler):
    state = ReceiveState.COMPLETE
    
    def execute(self, machine: ReceiveStateMachine) -> ReceiveState:
        # Terminal state - no transition
        return ReceiveState.COMPLETE
    
    def detect(self, machine: ReceiveStateMachine) -> bool:
        # Complete is determined by flow, not screen content
        return False


class ErrorHandler(StateHandler):
    state = ReceiveState.ERROR

    def execute(self, machine: ReceiveStateMachine) -> ReceiveState:
        # Attempt recovery if retries remaining
        if retry_with_context(machine.context):
            # Try to detect current state and continue from there
            detected = machine.detect_current_state()
            if detected != ReceiveState.ERROR:
                return detected

        machine.rf_capture("error", machine.context.error_message or "Error")
        return ReceiveState.ERROR

    def detect(self, machine: ReceiveStateMachine) -> bool:
        text = machine.read_screen_text()
        return 'error' in text or 'invalid' in text


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _parse_screen_quantities(machine: ReceiveStateMachine) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """Extract shipped/received quantities and iLPN from screen."""
    import re
    
    shipped = received = None
    ilpn = None
    
    try:
        text = machine.read_screen_text()
        
        # Parse quantities
        shipped_match = re.search(r'shpd?\s*:?\s*([\d,]+)', text, re.I)
        if shipped_match:
            shipped = int(shipped_match.group(1).replace(',', ''))
        
        received_match = re.search(r'rcvd?\s*:?\s*([\d,]+)', text, re.I)
        if received_match:
            received = int(received_match.group(1).replace(',', ''))
        
        # Parse iLPN
        ilpn_match = re.search(r'lpn[:\s"]*([A-Za-z0-9]+)', text, re.I)
        if ilpn_match:
            ilpn = ilpn_match.group(1)
            
    except Exception as e:
        rf_log(f"⚠️ Failed parsing screen quantities: {e}")
    
    return shipped, received, ilpn


def _read_suggested_location(machine: ReceiveStateMachine) -> str:
    """Read suggested location from screen."""
    import re
    
    # Try configured selectors first
    for key in ('suggested_location_aloc', 'suggested_location_cloc'):
        selector = machine.selectors.selectors.get(key)
        if not selector:
            continue
        try:
            loc = machine.rf.primitive.read_field(selector).replace('-', '').strip()
            if loc:
                return loc
        except Exception:
            continue
    
    # Fallback to text parsing
    try:
        text = machine.read_screen_text()
        match = re.search(r'[AC]LOC\s*:?\s*([A-Za-z0-9\-]+)', text, re.I)
        if match:
            return match.group(1).replace('-', '').strip()
    except Exception:
        pass
    
    return ""
