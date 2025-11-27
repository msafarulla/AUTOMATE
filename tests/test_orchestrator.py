"""
Tests for RF primitives and workflows.
"""
import pytest
from unittest.mock import MagicMock, patch, call

from operations.rf_primitives import RFPrimitives, RFWorkflows, RFMenuIntegration
from config.settings import Settings


class TestRFPrimitives:
    """Tests for RFPrimitives class."""

    @pytest.fixture
    def primitives(self, mock_page, mock_screenshot_mgr):
        """Create RF primitives instance."""
        get_iframe = MagicMock(return_value=mock_page.main_frame)
        return RFPrimitives(
            page=mock_page,
            get_iframe_func=get_iframe,
            screenshot_mgr=mock_screenshot_mgr,
        )

    def test_fill_and_submit_success(self, primitives, mock_page, mock_frame):
        """Test successful field fill and submit."""
        # Setup - configure the mock frame to return the mock input
        mock_input = MagicMock()
        mock_input.fill = MagicMock()
        mock_input.press = MagicMock()
        mock_input.wait_for = MagicMock()

        # Patch the locator method to return our mock
        original_locator = mock_frame.locator
        def custom_locator(selector):
            result = original_locator(selector)
            result.first = mock_input
            return result
        mock_frame.locator = custom_locator

        # Execute
        has_error, msg = primitives.fill_and_submit(
            selector="input#test",
            value="TEST123",
            screenshot_label="test_input",
            wait_for_change=False,
            check_errors=False,
        )

        # Verify
        assert not has_error
        assert msg is None
        mock_input.fill.assert_called_once_with("TEST123")
        mock_input.press.assert_called_once_with("Enter")

    def test_fill_and_submit_with_error(self, primitives, mock_page):
        """Test submit that triggers error screen."""
        # Setup - make body text show error
        primitives._check_for_errors = MagicMock(return_value=(True, "Invalid test data"))
        
        # Execute
        has_error, msg = primitives.fill_and_submit(
            selector="input#test",
            value="BADDATA",
            screenshot_label="test_error",
            wait_for_change=False,
            check_errors=True,
        )
        
        # Verify
        assert has_error
        assert "Invalid test data" in msg

    def test_read_field(self, primitives, mock_frame):
        """Test reading field value."""
        # Setup - configure mock frame to return specific text
        mock_frame._text = "  TEST VALUE  "

        # Execute
        value = primitives.read_field("span#value")

        # Verify
        assert value == "TEST VALUE"

    def test_read_field_with_transform(self, primitives, mock_frame):
        """Test reading field with transformation."""
        # Setup - configure mock frame to return specific text
        mock_frame._text = "A-01-02"

        # Execute
        value = primitives.read_field(
            "span#location",
            transform=lambda x: x.replace("-", "")
        )

        # Verify
        assert value == "A0102"

    def test_go_home_with_custom_reset(self, mock_page, mock_screenshot_mgr):
        """Test go_home with custom reset function."""
        custom_reset = MagicMock()
        get_iframe = MagicMock(return_value=mock_page.main_frame)
        
        primitives = RFPrimitives(
            page=mock_page,
            get_iframe_func=get_iframe,
            screenshot_mgr=mock_screenshot_mgr,
            reset_to_home=custom_reset,
        )
        
        primitives.go_home()
        custom_reset.assert_called_once()

    def test_accept_message(self, primitives, mock_page):
        """Test accept message keyboard shortcut."""
        primitives.accept_message()
        mock_page.keyboard.press.assert_called()


class TestRFWorkflows:
    """Tests for RFWorkflows class."""

    @pytest.fixture
    def workflows(self, mock_rf_primitives):
        """Create RF workflows instance."""
        return RFWorkflows(mock_rf_primitives)

    def test_navigate_to_menu_by_search_success(self, workflows, mock_rf_primitives):
        """Test successful menu navigation."""
        mock_rf_primitives.fill_and_submit.return_value = (False, None)
        
        result = workflows.navigate_to_menu_by_search("Receive", "1012408")
        
        assert result is True
        # Should call go_home, then search, then select option
        assert mock_rf_primitives.fill_and_submit.call_count >= 2

    def test_navigate_to_menu_by_search_failure(self, workflows, mock_rf_primitives):
        """Test menu navigation failure."""
        mock_rf_primitives.fill_and_submit.return_value = (True, "Not found")
        
        result = workflows.navigate_to_menu_by_search("BadMenu", "999999")
        
        assert result is False

    def test_scan_barcode_tracks_selector(self, workflows):
        """Test that scan_barcode tracks last scanned selector."""
        has_error, msg = workflows.scan_barcode(
            selector="input#asn",
            value="12345678",
            label="ASN",
        )
        
        assert not has_error
        assert workflows._last_scanned_selector == "input#asn"

    def test_scan_barcode_auto_enter(self, workflows, mock_rf_primitives):
        """Test auto-enter scan that clears selector tracking."""
        mock_rf_primitives.fill_and_submit.return_value = (False, None)
        
        has_error, msg = workflows.scan_barcode_auto_enter(
            selector="input#item",
            value="ITEM123",
            label="Item",
        )
        
        assert not has_error
        assert workflows._last_scanned_selector is None

    def test_press_enter_uses_last_selector(self, workflows, mock_rf_primitives):
        """Test press_enter uses tracked selector."""
        # First scan to set selector
        workflows._last_scanned_selector = "input#qty"
        mock_rf_primitives.submit_current_input.return_value = (False, None)
        
        workflows.press_enter("quantity")
        
        mock_rf_primitives.submit_current_input.assert_called_once()
        assert workflows._last_scanned_selector is None  # Should clear after

    def test_enter_quantity(self, workflows, mock_rf_primitives):
        """Test quantity entry."""
        mock_rf_primitives.fill_and_submit.return_value = (False, None)
        
        success = workflows.enter_quantity(
            selector="input#qty",
            qty=100,
            item_name="TESTITEM",
        )
        
        assert success
        mock_rf_primitives.fill_and_submit.assert_called_once()
        call_args = mock_rf_primitives.fill_and_submit.call_args
        assert call_args[1]["value"] == "100"

    def test_enter_quantity_with_context(self, workflows, mock_rf_primitives):
        """Test quantity entry includes context in screenshot."""
        mock_rf_primitives.fill_and_submit.return_value = (False, None)
        
        workflows.enter_quantity(
            selector="input#qty",
            qty=50,
            context={
                "shipped": 100,
                "received": 50,
                "ilpn": "LPN123",
            },
        )
        
        # Should include context in screenshot text
        call_args = mock_rf_primitives.fill_and_submit.call_args
        screenshot_text = call_args[1]["screenshot_text"]
        assert "shpd=100" in screenshot_text
        assert "ilpn=LPN123" in screenshot_text

    def test_scan_fields_and_submit(self, workflows, mock_rf_primitives):
        """Test scanning multiple fields and submitting."""
        workflows.scan_barcode = MagicMock(return_value=(False, None))
        workflows.press_enter = MagicMock(return_value=(False, None))
        
        scans = [
            ("input#field1", "VALUE1", "Field 1"),
            ("input#field2", "VALUE2", "Field 2"),
        ]
        
        has_error, msg = workflows.scan_fields_and_submit(
            scans,
            submit_label="test_submit",
        )
        
        assert not has_error
        assert workflows.scan_barcode.call_count == 2
        workflows.press_enter.assert_called_once_with("test_submit", wait_for_change=True)

    def test_confirm_location(self, workflows, mock_rf_primitives):
        """Test location confirmation."""
        mock_rf_primitives.fill_and_submit.return_value = (False, None)
        
        has_error, msg = workflows.confirm_location(
            selector="input#location",
            location="A0101",
        )
        
        assert not has_error
        mock_rf_primitives.fill_and_submit.assert_called_once()


class TestRFMenuIntegration:
    """Tests for RFMenuIntegration."""

    @pytest.fixture
    def rf_menu_manager(self, mock_page, mock_screenshot_mgr):
        """Create mock RF menu manager."""
        mgr = MagicMock()
        mgr.page = mock_page
        mgr.screenshot_mgr = mock_screenshot_mgr
        mgr.get_iframe = MagicMock(return_value=mock_page.main_frame)
        mgr.reset_to_home = MagicMock()
        return mgr

    def test_creates_primitives_and_workflows(self, rf_menu_manager):
        """Test integration creates both primitives and workflows."""
        integration = RFMenuIntegration(rf_menu_manager)
        
        assert integration.primitives is not None
        assert integration.workflows is not None
        assert isinstance(integration.workflows, RFWorkflows)

    def test_get_primitives(self, rf_menu_manager):
        """Test getting primitives."""
        integration = RFMenuIntegration(rf_menu_manager)
        primitives = integration.get_primitives()
        
        assert primitives is integration.primitives

    def test_get_workflows(self, rf_menu_manager):
        """Test getting workflows."""
        integration = RFMenuIntegration(rf_menu_manager)
        workflows = integration.get_workflows()
        
        assert workflows is integration.workflows

    def test_primitives_use_manager_components(self, rf_menu_manager):
        """Test primitives correctly use manager's page and iframe."""
        integration = RFMenuIntegration(rf_menu_manager)
        
        assert integration.primitives.page == rf_menu_manager.page
        assert integration.primitives.screenshot_mgr == rf_menu_manager.screenshot_mgr


class TestAutoAcceptBehavior:
    """Tests for auto-accept error message behavior."""

    def test_auto_accept_enabled_by_default(self, mock_page, mock_screenshot_mgr):
        """Test auto-accept is enabled from settings."""
        with patch.object(Settings.app, 'auto_accept_rf_messages', True):
            get_iframe = MagicMock(return_value=mock_page.main_frame)
            primitives = RFPrimitives(
                page=mock_page,
                get_iframe_func=get_iframe,
                screenshot_mgr=mock_screenshot_mgr,
            )
            
            assert primitives._auto_accept_errors is True

    def test_auto_accept_override_in_method(self, mock_rf_primitives):
        """Test method-level override of auto-accept."""
        mock_rf_primitives._should_auto_accept.return_value = False
        
        workflows = RFWorkflows(mock_rf_primitives)
        mock_rf_primitives.fill_and_submit.return_value = (False, "Info message")
        
        workflows.scan_barcode_auto_enter(
            "input#test",
            "VALUE",
            "Test",
            auto_accept_errors=False,
        )
        
        # Should not have called accept_message
        mock_rf_primitives.accept_message.assert_not_called()

    def test_invalid_test_data_not_auto_accepted(self, mock_rf_primitives):
        """Test that invalid test data sentinel is not auto-accepted."""
        # Use a real RFWorkflows instance with mocked primitives
        workflows = RFWorkflows(mock_rf_primitives)

        mock_rf_primitives._should_auto_accept.return_value = True
        mock_rf_primitives.fill_and_submit.return_value = (
            True,
            RFPrimitives.INVALID_TEST_DATA_MSG
        )

        has_error, msg = workflows.scan_barcode_auto_enter(
            "input#test",
            "BAD",
            "Test",
        )

        # Should have error but not auto-accept
        assert has_error
        mock_rf_primitives.accept_message.assert_not_called()