"""
Tests for the receive state machine.
"""
import pytest
from unittest.mock import MagicMock, patch

from operations.inbound.receive_state_machine import (
    ReceiveStateMachine,
    ReceiveState,
    ReceiveContext,
    InitHandler,
    QtyEnteredHandler,
)
from config.operations_config import OperationConfig


class TestReceiveContext:
    """Tests for ReceiveContext dataclass."""

    def test_default_values(self):
        ctx = ReceiveContext()
        assert ctx.asn == ""
        assert ctx.item == ""
        assert ctx.quantity == 0
        assert ctx.retry_count == 0
        assert ctx.max_retries == 2
        assert ctx.transitions == []

    def test_record_transition(self):
        ctx = ReceiveContext()
        ctx.record_transition(ReceiveState.INIT, ReceiveState.NAVIGATED, "test")
        
        assert len(ctx.transitions) == 1
        assert ctx.transitions[0] == (ReceiveState.INIT, ReceiveState.NAVIGATED, "test")

    def test_multiple_transitions(self):
        ctx = ReceiveContext()
        ctx.record_transition(ReceiveState.INIT, ReceiveState.NAVIGATED, "nav")
        ctx.record_transition(ReceiveState.NAVIGATED, ReceiveState.ASN_SCANNED, "asn")
        
        assert len(ctx.transitions) == 2


class TestReceiveStateMachine:
    """Tests for the main state machine."""

    @pytest.fixture
    def machine(self, mock_rf_workflows, mock_screenshot_mgr):
        """Create a state machine with mocked dependencies."""
        return ReceiveStateMachine(
            rf=mock_rf_workflows,
            screenshot_mgr=mock_screenshot_mgr,
            selectors=OperationConfig.RECEIVE_SELECTORS,
        )

    def test_initial_state(self, machine):
        assert machine.state == ReceiveState.INIT

    def test_handlers_registered(self, machine):
        assert ReceiveState.INIT in machine.handlers
        assert ReceiveState.NAVIGATED in machine.handlers
        assert ReceiveState.COMPLETE in machine.handlers
        assert ReceiveState.ERROR in machine.handlers

    def test_is_terminal_states(self, machine):
        machine.state = ReceiveState.INIT
        assert not machine._is_terminal()

        machine.state = ReceiveState.COMPLETE
        assert machine._is_terminal()

        machine.state = ReceiveState.ERROR
        assert machine._is_terminal()

        machine.state = ReceiveState.ABORTED
        assert machine._is_terminal()

    def test_transition_recording(self, machine):
        machine.context = ReceiveContext()
        machine._transition_to(ReceiveState.NAVIGATED, "test reason")
        
        assert machine.state == ReceiveState.NAVIGATED
        assert len(machine.context.transitions) == 1

    def test_no_duplicate_transition(self, machine):
        """Same state transition should not be recorded."""
        machine.context = ReceiveContext()
        machine.state = ReceiveState.NAVIGATED
        machine._transition_to(ReceiveState.NAVIGATED, "same state")
        
        assert len(machine.context.transitions) == 0


class TestQtyEnteredHandler:
    """Tests for the critical branching handler."""

    @pytest.fixture
    def handler(self):
        return QtyEnteredHandler()

    @pytest.fixture
    def machine_with_location(self, mock_rf_workflows, mock_screenshot_mgr):
        """Machine that will detect location prompt."""
        machine = ReceiveStateMachine(
            rf=mock_rf_workflows,
            screenshot_mgr=mock_screenshot_mgr,
            selectors=OperationConfig.RECEIVE_SELECTORS,
        )
        machine.context = ReceiveContext(asn="12345678", item="TEST", quantity=100)
        # Mock to return location screen text
        machine.read_screen_text = MagicMock(return_value="aloc: A-01-01")
        machine.is_element_visible = MagicMock(return_value=True)
        return machine

    def test_detects_location_prompt(self, handler, machine_with_location):
        result = handler.execute(machine_with_location)
        assert result == ReceiveState.AWAITING_LOCATION

    def test_detects_blind_ilpn(self, handler, mock_rf_workflows, mock_screenshot_mgr):
        machine = ReceiveStateMachine(
            rf=mock_rf_workflows,
            screenshot_mgr=mock_screenshot_mgr,
            selectors=OperationConfig.RECEIVE_SELECTORS,
        )
        machine.context = ReceiveContext()
        machine.read_screen_text = MagicMock(return_value="blind ilpn required")
        machine.is_element_visible = MagicMock(side_effect=lambda sel, **kw: "lpn" in sel.lower())
        
        result = handler.execute(machine)
        assert result == ReceiveState.AWAITING_BLIND_ILPN

    def test_flow_deviation_detection(self, handler, machine_with_location):
        """Test that flow deviations are detected when hint doesn't match."""
        machine_with_location.context.flow_hint = "IB_RULE_EXCEPTION_BLIND_ILPN"
        machine_with_location.context.auto_handle_deviation = False
        
        result = handler.execute(machine_with_location)
        
        # Should error because expected blind ILPN but got location
        assert result == ReceiveState.ERROR

    def test_invokes_detour_after_qty(self, handler, machine_with_location):
        mock_detours = MagicMock()
        mock_detours.run.return_value = True
        machine_with_location.detours = mock_detours

        result = handler.execute(machine_with_location)

        assert result == ReceiveState.AWAITING_LOCATION
        mock_detours.run.assert_called_once_with("post_qty", context=machine_with_location.context)
        assert "deviation" in (machine_with_location.context.error_message or "").lower()


class TestInitHandler:
    """Tests for initialization handler."""

    @pytest.fixture
    def handler(self):
        return InitHandler()

    def test_successful_navigation(self, handler, mock_rf_workflows, mock_screenshot_mgr):
        machine = ReceiveStateMachine(
            rf=mock_rf_workflows,
            screenshot_mgr=mock_screenshot_mgr,
            selectors=OperationConfig.RECEIVE_SELECTORS,
        )
        mock_rf_workflows.navigate_to_menu_by_search.return_value = True
        
        result = handler.execute(machine)
        assert result == ReceiveState.NAVIGATED

    def test_failed_navigation(self, handler, mock_rf_workflows, mock_screenshot_mgr):
        machine = ReceiveStateMachine(
            rf=mock_rf_workflows,
            screenshot_mgr=mock_screenshot_mgr,
            selectors=OperationConfig.RECEIVE_SELECTORS,
        )
        mock_rf_workflows.navigate_to_menu_by_search.return_value = False
        
        result = handler.execute(machine)
        assert result == ReceiveState.ERROR


class TestFullWorkflow:
    """Integration-style tests for complete workflows."""

    def test_happy_path_workflow(self, mock_rf_workflows, mock_screenshot_mgr):
        """Test complete happy path from init to complete."""
        machine = ReceiveStateMachine(
            rf=mock_rf_workflows,
            screenshot_mgr=mock_screenshot_mgr,
            selectors=OperationConfig.RECEIVE_SELECTORS,
        )

        # Mock all the workflow methods to succeed
        mock_rf_workflows.navigate_to_menu_by_search.return_value = True
        mock_rf_workflows.scan_barcode_auto_enter.return_value = (False, None)
        mock_rf_workflows.enter_quantity.return_value = True
        mock_rf_workflows.confirm_location.return_value = (False, None)

        # Mock read_screen_text to return location prompt after qty
        def mock_read():
            if machine.state == ReceiveState.QTY_ENTERED:
                return "aloc: A-01-01"
            return ""

        # Mock is_element_visible
        def mock_visible(sel, **kw):
            if machine.state == ReceiveState.QTY_ENTERED:
                return "location" in sel.lower() or "locn" in sel.lower()
            return True

        machine.read_screen_text = mock_read
        machine.is_element_visible = mock_visible

        # Mock reading suggested location
        mock_rf_workflows.rf.read_field.return_value = "A0101"

        success = machine.run(
            asn="12345678",
            item="TESTITEM",
            quantity=100,
            flow_hint="HAPPY_PATH",
        )

        assert success
        assert machine.state == ReceiveState.COMPLETE
        assert len(machine.context.transitions) > 0

    def test_error_recovery_with_retry(self, mock_rf_workflows, mock_screenshot_mgr):
        """Test that errors trigger retry logic."""
        machine = ReceiveStateMachine(
            rf=mock_rf_workflows,
            screenshot_mgr=mock_screenshot_mgr,
            selectors=OperationConfig.RECEIVE_SELECTORS,
        )
        
        # Navigation always fails
        mock_rf_workflows.navigate_to_menu_by_search.return_value = False

        success = machine.run(
            asn="12345678",
            item="TESTITEM",
            quantity=100,
        )

        assert not success
        assert machine.state == ReceiveState.ERROR
