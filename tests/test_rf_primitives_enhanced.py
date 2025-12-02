"""
Enhanced tests for operations/rf_primitives.py to improve coverage.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from operations.rf_primitives import RFPrimitives, RFWorkflows


class TestRFPrimitivesEnhanced:
    """Enhanced tests for RFPrimitives class focusing on untested paths."""

    @pytest.fixture
    def mock_page(self):
        """Create mock page."""
        mock = MagicMock()
        mock.main_frame = MagicMock()
        mock.keyboard = MagicMock()
        mock.wait_for_timeout = MagicMock()
        return mock

    @pytest.fixture
    def mock_screenshot_mgr(self):
        """Create mock screenshot manager."""
        return MagicMock()

    @pytest.fixture
    def mock_iframe(self):
        """Create mock iframe."""
        mock = MagicMock()
        mock.locator = MagicMock()
        return mock

    @pytest.fixture
    def primitives(self, mock_page, mock_screenshot_mgr, mock_iframe):
        """Create RF primitives instance."""
        get_iframe = MagicMock(return_value=mock_iframe)
        return RFPrimitives(
            page=mock_page,
            get_iframe_func=get_iframe,
            screenshot_mgr=mock_screenshot_mgr,
        )

    def test_should_auto_accept_uses_default(self, primitives):
        """Test _should_auto_accept returns default when no override."""
        result = primitives._should_auto_accept(None)
        assert isinstance(result, bool)

    def test_should_auto_accept_uses_override(self, primitives):
        """Test _should_auto_accept returns override value."""
        assert primitives._should_auto_accept(True) is True
        assert primitives._should_auto_accept(False) is False

    def test_fill_capture_submit_no_screen_change(self, primitives, mock_iframe):
        """Test fill_capture_submit when screen doesn't change."""
        mock_input = MagicMock()
        mock_locator = MagicMock()
        mock_locator.first = mock_input
        mock_iframe.locator.return_value = mock_locator

        with patch('operations.rf_primitives.HashUtils') as mock_hash, \
             patch('operations.rf_primitives.WaitUtils') as mock_wait:
            mock_hash.get_frame_snapshot.return_value = "snapshot"
            mock_wait.wait_for_screen_change.return_value = False

            has_error, msg = primitives.fill_capture_submit(
                selector="input#test",
                value="VALUE",
                screenshot_label="test",
                wait_for_change=True
            )

            assert has_error is True
            assert "Screen did not change" in msg

    def test_fill_capture_submit_with_screen_change_and_error(self, primitives, mock_iframe):
        """Test fill_capture_submit with screen change but error detected."""
        mock_input = MagicMock()
        mock_locator = MagicMock()
        mock_locator.first = mock_input
        mock_iframe.locator.return_value = mock_locator

        with patch('operations.rf_primitives.HashUtils') as mock_hash, \
             patch('operations.rf_primitives.WaitUtils') as mock_wait, \
             patch.object(primitives, '_check_for_errors', return_value=(True, "Test error")):
            mock_hash.get_frame_snapshot.return_value = "snapshot"
            mock_wait.wait_for_screen_change.return_value = True

            has_error, msg = primitives.fill_capture_submit(
                selector="input#test",
                value="VALUE",
                screenshot_label="test",
                check_errors=True
            )

            assert has_error is True
            assert msg == "Test error"

    def test_fill_field_returns_input(self, primitives, mock_iframe):
        """Test fill_field returns the input locator."""
        mock_input = MagicMock()
        mock_locator = MagicMock()
        mock_locator.first = mock_input
        mock_iframe.locator.return_value = mock_locator

        result = primitives.fill_field(
            selector="input#test",
            value="VALUE",
            screenshot_label="test"
        )

        assert result is mock_input
        mock_input.fill.assert_called_once_with("VALUE")

    def test_fill_field_with_custom_screenshot_text(self, primitives, mock_iframe, mock_screenshot_mgr):
        """Test fill_field with custom screenshot text."""
        mock_input = MagicMock()
        mock_locator = MagicMock()
        mock_locator.first = mock_input
        mock_iframe.locator.return_value = mock_locator

        primitives.fill_field(
            selector="input#test",
            value="VALUE",
            screenshot_label="test",
            screenshot_text="Custom text"
        )

        mock_screenshot_mgr.capture_rf_window.assert_called_once()
        call_args = mock_screenshot_mgr.capture_rf_window.call_args
        assert call_args[0][2] == "Custom text"

    def test_submit_current_input_with_selector(self, primitives, mock_iframe):
        """Test submit_current_input with explicit selector."""
        mock_input = MagicMock()
        mock_locator = MagicMock()
        mock_locator.first = mock_input
        mock_iframe.locator.return_value = mock_locator

        with patch('operations.rf_primitives.HashUtils'), \
             patch('operations.rf_primitives.WaitUtils'), \
             patch.object(primitives, '_check_for_errors', return_value=(False, None)):

            has_error, msg = primitives.submit_current_input(
                screenshot_label="test",
                selector="input#custom",
                check_errors=True
            )

            assert has_error is False
            assert msg is None
            mock_iframe.locator.assert_called_with("input#custom")

    def test_submit_current_input_without_selector(self, primitives, mock_iframe):
        """Test submit_current_input uses focused element when no selector."""
        mock_input = MagicMock()
        mock_locator = MagicMock()
        mock_locator.first = mock_input
        mock_iframe.locator.return_value = mock_locator

        with patch('operations.rf_primitives.HashUtils'), \
             patch('operations.rf_primitives.WaitUtils'), \
             patch.object(primitives, '_check_for_errors', return_value=(False, None)):

            primitives.submit_current_input(
                screenshot_label="test",
                selector=None,
                wait_for_change=False,
                check_errors=False
            )

            mock_iframe.locator.assert_called_with(":focus")

    def test_read_field_with_transform(self, primitives, mock_iframe):
        """Test read_field applies transform function."""
        mock_locator = MagicMock()
        mock_locator.inner_text.return_value = "  VALUE  "
        mock_iframe.locator.return_value = mock_locator

        result = primitives.read_field(
            selector="div.value",
            transform=lambda x: x.upper()
        )

        assert result == "VALUE"

    def test_read_field_without_transform(self, primitives, mock_iframe):
        """Test read_field without transform function."""
        mock_locator = MagicMock()
        mock_locator.inner_text.return_value = "  Value  "
        mock_iframe.locator.return_value = mock_locator

        result = primitives.read_field(selector="div.value")

        assert result == "Value"

    def test_select_menu_option(self, primitives):
        """Test select_menu_option calls fill_capture_submit correctly."""
        with patch.object(primitives, 'fill_capture_submit', return_value=(False, None)) as mock_fill:
            has_error, msg = primitives.select_menu_option("3", "Test Menu")

            mock_fill.assert_called_once()
            call_args = mock_fill.call_args
            assert call_args[1]['value'] == "3"
            assert "Test Menu" in call_args[1]['screenshot_label']

    def test_press_rf_hot_key_with_wait(self, primitives, mock_page, mock_iframe):
        """Test press_rf_hot_key with wait_for_change."""
        mock_body = MagicMock()
        mock_locator = MagicMock()
        mock_locator.first = mock_body
        mock_iframe.locator.return_value = mock_locator

        with patch('operations.rf_primitives.HashUtils'), \
             patch('operations.rf_primitives.WaitUtils'):
            primitives.press_rf_hot_key(
                key="Control+a",
                screenshot_label="test",
                wait_for_change=True
            )

            mock_page.keyboard.press.assert_called_once_with("Control+a")
            mock_body.focus.assert_called_once()

    def test_press_rf_hot_key_without_wait(self, primitives, mock_page, mock_iframe):
        """Test press_rf_hot_key without wait_for_change."""
        mock_body = MagicMock()
        mock_locator = MagicMock()
        mock_locator.first = mock_body
        mock_iframe.locator.return_value = mock_locator

        primitives.press_rf_hot_key(
            key="Control+b",
            screenshot_label="test",
            wait_for_change=False
        )

        mock_page.keyboard.press.assert_called_once_with("Control+b")

    def test_press_rf_hot_key_focus_failure(self, primitives, mock_iframe):
        """Test press_rf_hot_key raises error when focus fails."""
        mock_locator = MagicMock()
        mock_locator.first.focus.side_effect = Exception("Focus failed")
        mock_iframe.locator.return_value = mock_locator

        with pytest.raises(RuntimeError, match="Failed to focus iframe"):
            primitives.press_rf_hot_key(
                key="Control+a",
                screenshot_label="test"
            )

    def test_go_home_with_reset_function(self, mock_page, mock_screenshot_mgr, mock_iframe):
        """Test go_home uses reset_to_home function when provided."""
        reset_func = MagicMock()
        get_iframe = MagicMock(return_value=mock_iframe)
        primitives = RFPrimitives(
            page=mock_page,
            get_iframe_func=get_iframe,
            screenshot_mgr=mock_screenshot_mgr,
            reset_to_home=reset_func
        )

        primitives.go_home()

        reset_func.assert_called_once()

    def test_go_home_without_reset_function(self, primitives):
        """Test go_home uses hotkey when no reset function provided."""
        with patch.object(primitives, 'press_rf_hot_key') as mock_hotkey:
            primitives.go_home()

            mock_hotkey.assert_called_once_with("Control+b", "RF_HOME", "RF Home")

    def test_accept_message(self, primitives):
        """Test accept_message calls press_rf_hot_key."""
        with patch.object(primitives, 'press_rf_hot_key') as mock_hotkey:
            primitives.accept_message()

            mock_hotkey.assert_called_once_with("Control+a", "accepted_message", "Accepted/Proceeded")

    def test_check_for_errors_detects_error(self, primitives, mock_page, mock_iframe):
        """Test _check_for_errors detects error keywords."""
        mock_body = MagicMock()
        mock_body.inner_text.return_value = "Error: Invalid input"
        mock_iframe.locator.return_value = mock_body

        with patch('operations.rf_primitives.WaitUtils'):
            has_error, msg = primitives._check_for_errors()

            assert has_error is True
            assert "Invalid input" in msg

    def test_check_for_errors_detects_invalid(self, primitives, mock_page, mock_iframe):
        """Test _check_for_errors detects invalid keyword."""
        mock_body = MagicMock()
        mock_body.inner_text.return_value = "Invalid data entered"
        mock_iframe.locator.return_value = mock_body

        with patch('operations.rf_primitives.WaitUtils'):
            has_error, msg = primitives._check_for_errors()

            assert has_error is True
            assert "Invalid" in msg

    def test_check_for_errors_detects_info(self, primitives, mock_page, mock_iframe):
        """Test _check_for_errors detects info messages (not errors)."""
        mock_body = MagicMock()
        mock_body.inner_text.return_value = "Info: Operation completed"
        mock_iframe.locator.return_value = mock_body

        with patch('operations.rf_primitives.WaitUtils'):
            has_error, msg = primitives._check_for_errors()

            assert has_error is False
            assert "Operation completed" in msg

    def test_check_for_errors_detects_warning(self, primitives, mock_page, mock_iframe):
        """Test _check_for_errors detects warning messages (not errors)."""
        mock_body = MagicMock()
        mock_body.inner_text.return_value = "Warning: Low inventory"
        mock_iframe.locator.return_value = mock_body

        with patch('operations.rf_primitives.WaitUtils'):
            has_error, msg = primitives._check_for_errors()

            assert has_error is False
            assert "Low inventory" in msg

    def test_check_for_errors_no_error(self, primitives, mock_page, mock_iframe):
        """Test _check_for_errors returns False when no error."""
        mock_body = MagicMock()
        mock_body.inner_text.return_value = "Operation successful"
        mock_iframe.locator.return_value = mock_body

        with patch('operations.rf_primitives.WaitUtils'):
            has_error, msg = primitives._check_for_errors()

            assert has_error is False
            assert msg is None

    def test_check_for_errors_exception_handling(self, primitives, mock_iframe):
        """Test _check_for_errors handles exceptions gracefully."""
        mock_iframe.locator.side_effect = Exception("Locator failed")

        with patch('operations.rf_primitives.WaitUtils'):
            has_error, msg = primitives._check_for_errors()

            assert has_error is False
            assert msg is None


class TestRFWorkflowsEnhanced:
    """Enhanced tests for RFWorkflows class."""

    @pytest.fixture
    def mock_primitives(self):
        """Create mock RF primitives."""
        mock = MagicMock()
        mock.INVALID_TEST_DATA_MSG = "Invalid test data"
        return mock

    @pytest.fixture
    def workflows(self, mock_primitives):
        """Create RF workflows instance."""
        return RFWorkflows(mock_primitives)

    def test_is_invalid_test_data_true(self, workflows):
        """Test _is_invalid_test_data returns True for sentinel."""
        assert workflows._is_invalid_test_data("Invalid test data") is True
        assert workflows._is_invalid_test_data("  INVALID TEST DATA  ") is True

    def test_is_invalid_test_data_false(self, workflows):
        """Test _is_invalid_test_data returns False for other messages."""
        assert workflows._is_invalid_test_data("Other error") is False
        assert workflows._is_invalid_test_data("") is False
        assert workflows._is_invalid_test_data(None) is False

    def test_navigate_to_screen_success(self, workflows, mock_primitives):
        """Test navigate_to_screen with successful navigation."""
        mock_primitives.go_home = MagicMock()
        mock_primitives.select_menu_option.return_value = (False, None)

        path = [("1", "Menu1"), ("2", "Menu2")]
        workflows.navigate_to_screen(path)

        mock_primitives.go_home.assert_called_once()
        assert mock_primitives.select_menu_option.call_count == 2

    def test_navigate_to_screen_failure(self, workflows, mock_primitives):
        """Test navigate_to_screen raises error on failure."""
        mock_primitives.go_home = MagicMock()
        mock_primitives.select_menu_option.return_value = (True, "Navigation error")

        path = [("1", "Menu1")]

        with pytest.raises(RuntimeError, match="Navigation failed"):
            workflows.navigate_to_screen(path)

    def test_navigate_to_menu_by_search_without_tran_id(self, workflows, mock_primitives):
        """Test navigate_to_menu_by_search without tran id check."""
        mock_primitives.go_home = MagicMock()
        mock_primitives.press_rf_hot_key = MagicMock()
        mock_primitives.fill_capture_submit.return_value = (False, None)

        with patch('operations.rf_primitives.Settings') as mock_settings:
            mock_settings.app.show_tran_id = False

            result = workflows.navigate_to_menu_by_search("RECEIVE")

            assert result is True
            mock_primitives.go_home.assert_called_once()
            mock_primitives.press_rf_hot_key.assert_called_once()

    def test_navigate_to_menu_by_search_with_tran_id_match(self, workflows, mock_primitives):
        """Test navigate_to_menu_by_search with matching tran id."""
        mock_primitives.go_home = MagicMock()
        mock_primitives.press_rf_hot_key = MagicMock()
        mock_primitives.fill_capture_submit.return_value = (False, None)
        mock_primitives.read_field.return_value = "1) RECEIVE #RF01"

        with patch('operations.rf_primitives.Settings') as mock_settings:
            mock_settings.app.show_tran_id = True

            result = workflows.navigate_to_menu_by_search("RECEIVE", expected_tran_id="RF01")

            assert result is True

    def test_navigate_to_menu_by_search_with_tran_id_mismatch(self, workflows, mock_primitives):
        """Test navigate_to_menu_by_search with mismatched tran id."""
        mock_primitives.go_home = MagicMock()
        mock_primitives.press_rf_hot_key = MagicMock()
        mock_primitives.fill_capture_submit.return_value = (False, None)
        mock_primitives.read_field.return_value = "1) RECEIVE #RF01"
        mock_primitives.screenshot_mgr = MagicMock()
        mock_primitives.page = MagicMock()

        with patch('operations.rf_primitives.Settings') as mock_settings:
            mock_settings.app.show_tran_id = True

            result = workflows.navigate_to_menu_by_search("RECEIVE", expected_tran_id="RF02")

            assert result is False

    def test_navigate_to_menu_by_search_read_failure(self, workflows, mock_primitives):
        """Test navigate_to_menu_by_search handles read failure."""
        mock_primitives.go_home = MagicMock()
        mock_primitives.press_rf_hot_key = MagicMock()
        mock_primitives.fill_capture_submit.return_value = (False, None)
        mock_primitives.read_field.side_effect = Exception("Read failed")
        mock_primitives.screenshot_mgr = MagicMock()
        mock_primitives.page = MagicMock()

        with patch('operations.rf_primitives.Settings') as mock_settings:
            mock_settings.app.show_tran_id = True

            result = workflows.navigate_to_menu_by_search("RECEIVE", expected_tran_id="RF01")

            assert result is False

    def test_navigate_to_menu_by_search_first_fill_error(self, workflows, mock_primitives):
        """Test navigate_to_menu_by_search handles first fill error."""
        mock_primitives.go_home = MagicMock()
        mock_primitives.press_rf_hot_key = MagicMock()
        mock_primitives.fill_capture_submit.return_value = (True, "Search failed")
        mock_primitives.screenshot_mgr = MagicMock()
        mock_primitives.page = MagicMock()

        result = workflows.navigate_to_menu_by_search("RECEIVE")

        assert result is False

    def test_navigate_to_menu_by_search_second_fill_error(self, workflows, mock_primitives):
        """Test navigate_to_menu_by_search handles second fill error."""
        mock_primitives.go_home = MagicMock()
        mock_primitives.press_rf_hot_key = MagicMock()
        mock_primitives.fill_capture_submit.side_effect = [(False, None), (True, "Select failed")]

        result = workflows.navigate_to_menu_by_search("RECEIVE")

        assert result is False

    def test_scan_barcode_tracks_selector(self, workflows, mock_primitives):
        """Test scan_barcode tracks last selector."""
        mock_primitives.fill_field = MagicMock()

        workflows.scan_barcode("input#lpn", "LPN123", "LPN")

        assert workflows._last_scanned_selector == "input#lpn"

    def test_scan_barcode_auto_enter_clears_selector(self, workflows, mock_primitives):
        """Test scan_barcode_auto_enter clears last selector."""
        mock_primitives.fill_capture_submit.return_value = (False, None)
        mock_primitives._should_auto_accept.return_value = False

        workflows._last_scanned_selector = "input#previous"
        workflows.scan_barcode_auto_enter("input#lpn", "LPN123", "LPN")

        assert workflows._last_scanned_selector is None

    def test_scan_barcode_auto_enter_with_auto_accept(self, workflows, mock_primitives):
        """Test scan_barcode_auto_enter with auto_accept enabled."""
        mock_primitives.fill_capture_submit.return_value = (True, "Some error")
        mock_primitives._should_auto_accept.return_value = True
        mock_primitives.accept_message = MagicMock()

        workflows.scan_barcode_auto_enter("input#lpn", "LPN123", "LPN")

        mock_primitives.accept_message.assert_called_once()

    def test_press_enter_without_tracked_selector(self, workflows, mock_primitives):
        """Test press_enter without tracked selector."""
        mock_primitives.submit_current_input.return_value = (False, None)
        mock_primitives._should_auto_accept.return_value = False

        workflows._last_scanned_selector = None
        workflows.press_enter("Submit")

        mock_primitives.submit_current_input.assert_called_once()
        call_args = mock_primitives.submit_current_input.call_args
        assert call_args[1]['selector'] is None

    def test_press_enter_with_tracked_selector(self, workflows, mock_primitives):
        """Test press_enter with tracked selector."""
        mock_primitives.submit_current_input.return_value = (False, None)
        mock_primitives._should_auto_accept.return_value = False

        workflows._last_scanned_selector = "input#lpn"
        workflows.press_enter("Submit")

        call_args = mock_primitives.submit_current_input.call_args
        assert call_args[1]['selector'] == "input#lpn"
        assert workflows._last_scanned_selector is None

    def test_press_enter_with_auto_accept(self, workflows, mock_primitives):
        """Test press_enter with auto_accept enabled."""
        mock_primitives.submit_current_input.return_value = (True, "Error message")
        mock_primitives._should_auto_accept.return_value = True
        mock_primitives.accept_message = MagicMock()

        workflows.press_enter("Submit", auto_accept_errors=True)

        mock_primitives.accept_message.assert_called_once()
