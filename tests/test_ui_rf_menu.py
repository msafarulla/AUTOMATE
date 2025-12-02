"""
Comprehensive tests for UI RF Menu (ui/rf_menu.py).
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from ui.rf_menu import RFMenuManager


class TestRFMenuManagerInitialization:
    """Test suite for RFMenuManager initialization."""

    def test_rf_menu_manager_init_defaults(self):
        """Test RFMenuManager initialization with defaults."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)

        assert rf_mgr.page == mock_page
        assert rf_mgr.page_mgr == mock_page_mgr
        assert rf_mgr.screenshot_mgr == mock_screenshot
        assert rf_mgr.verbose_logging is False
        assert rf_mgr._auto_click_info_icon is True
        assert rf_mgr._show_tran_id is False

    def test_rf_menu_manager_init_custom_params(self):
        """Test RFMenuManager with custom parameters."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        rf_mgr = RFMenuManager(
            mock_page,
            mock_page_mgr,
            mock_screenshot,
            verbose_logging=True,
            auto_click_info_icon=False,
            show_tran_id=True
        )

        assert rf_mgr.verbose_logging is True
        assert rf_mgr._auto_click_info_icon is False
        assert rf_mgr._show_tran_id is True
        assert rf_mgr._show_tran_id_completed is False


class TestRFMenuManagerIframe:
    """Test suite for iframe management."""

    def test_get_iframe(self):
        """Test getting RF iframe."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_page_mgr.get_rf_iframe.return_value = mock_iframe

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)
        iframe = rf_mgr.get_iframe()

        assert iframe == mock_iframe
        mock_page_mgr.get_rf_iframe.assert_called_once()


class TestRFMenuManagerResetHome:
    """Test suite for reset to home functionality."""

    @patch('ui.rf_menu.WaitUtils')
    @patch('ui.rf_menu.HashUtils')
    def test_reset_to_home_basic(self, mock_hash, mock_wait):
        """Test basic reset to home."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_body = MagicMock()
        mock_iframe.locator.return_value = mock_body
        mock_page_mgr.get_rf_iframe.return_value = mock_iframe

        mock_hash.get_frame_snapshot.return_value = "snapshot1"

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)
        rf_mgr.reset_to_home()

        # Should press Ctrl+B
        mock_page.keyboard.press.assert_called_with("Control+b")
        mock_screenshot.capture_rf_window.assert_called()

    @patch('ui.rf_menu.WaitUtils')
    @patch('ui.rf_menu.HashUtils')
    def test_reset_to_home_with_tran_id(self, mock_hash, mock_wait):
        """Test reset to home with transaction ID display."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_body = MagicMock()
        mock_iframe.locator.return_value = mock_body
        mock_page_mgr.get_rf_iframe.return_value = mock_iframe

        mock_hash.get_frame_snapshot.return_value = "snapshot1"

        rf_mgr = RFMenuManager(
            mock_page,
            mock_page_mgr,
            mock_screenshot,
            show_tran_id=True
        )
        rf_mgr._home_menu_has_hash = MagicMock(side_effect=[False, True])

        rf_mgr.reset_to_home()

        # Should press Ctrl+B and Ctrl+P
        assert mock_page.keyboard.press.call_count >= 2


class TestRFMenuManagerEnterChoice:
    """Test suite for entering choices."""

    @patch('ui.rf_menu.WaitUtils')
    @patch('ui.rf_menu.HashUtils')
    def test_enter_choice_success(self, mock_hash, mock_wait):
        """Test entering a choice successfully."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_input = MagicMock()
        mock_iframe.locator.return_value.first = mock_input
        mock_page_mgr.get_rf_iframe.return_value = mock_iframe

        mock_hash.get_frame_snapshot.return_value = "snapshot1"

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)
        rf_mgr.check_for_response = MagicMock(return_value=(False, None))

        has_error, msg = rf_mgr.enter_choice("1", "Menu Option 1")

        mock_input.fill.assert_called_once_with("1")
        mock_input.press.assert_called_once_with("Enter")
        assert has_error is False

    @patch('ui.rf_menu.WaitUtils')
    @patch('ui.rf_menu.HashUtils')
    def test_enter_choice_with_error(self, mock_hash, mock_wait):
        """Test entering choice that results in error."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_input = MagicMock()
        mock_iframe.locator.return_value.first = mock_input
        mock_page_mgr.get_rf_iframe.return_value = mock_iframe

        mock_hash.get_frame_snapshot.return_value = "snapshot1"

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)
        rf_mgr.check_for_response = MagicMock(return_value=(True, "Error: Invalid choice"))

        has_error, msg = rf_mgr.enter_choice("99", "Invalid")

        assert has_error is True
        assert "Error" in msg


class TestRFMenuManagerCheckResponse:
    """Test suite for checking RF responses."""

    @patch('ui.rf_menu.WaitUtils')
    def test_check_for_response_no_error(self, mock_wait):
        """Test checking response with no error."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_iframe.locator.return_value.inner_text.return_value = "Success message"

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)

        has_error, msg = rf_mgr.check_for_response(mock_iframe)

        assert has_error is False

    @patch('ui.rf_menu.WaitUtils')
    def test_check_for_response_with_error(self, mock_wait):
        """Test checking response with error."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_iframe.locator.return_value.inner_text.return_value = "Error: Invalid input data"

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)
        rf_mgr._capture_response_screen = MagicMock()

        has_error, msg = rf_mgr.check_for_response(mock_iframe)

        assert has_error is True
        assert "Error" in msg

    @patch('ui.rf_menu.WaitUtils')
    def test_check_for_response_with_warning(self, mock_wait):
        """Test checking response with warning."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_iframe.locator.return_value.inner_text.return_value = "Warning: Check quantity"

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)
        rf_mgr._capture_response_screen = MagicMock()

        has_error, msg = rf_mgr.check_for_response(mock_iframe)

        assert has_error is False
        assert "Warning" in msg


class TestRFMenuManagerAcceptProceed:
    """Test suite for accept/proceed functionality."""

    @patch('ui.rf_menu.WaitUtils')
    @patch('ui.rf_menu.HashUtils')
    def test_accept_proceed_with_error(self, mock_hash, mock_wait):
        """Test accepting/proceeding from error screen."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_iframe.locator.return_value.count.return_value = 1  # Error present
        mock_iframe.locator.return_value.first.focus = MagicMock()

        mock_hash.get_frame_snapshot.return_value = "snapshot1"

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)

        result = rf_mgr.accept_proceed(mock_iframe)

        assert result is True
        mock_page.keyboard.press.assert_called_with("Control+a")

    @patch('ui.rf_menu.WaitUtils')
    def test_accept_proceed_no_error(self, mock_wait):
        """Test accept when no error present."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_iframe.locator.return_value.count.return_value = 0  # No error

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)

        result = rf_mgr.accept_proceed(mock_iframe)

        assert result is False


class TestRFMenuManagerInfoIcon:
    """Test suite for info icon functionality."""

    @patch('ui.rf_menu.WaitUtils')
    @patch('ui.rf_menu.HashUtils')
    def test_click_info_icon_found(self, mock_hash, mock_wait):
        """Test clicking info icon when present."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_icon = MagicMock()
        mock_iframe.locator.return_value.first = mock_icon
        mock_page_mgr.get_rf_iframe.return_value = mock_iframe

        mock_hash.get_frame_snapshot.return_value = "snapshot1"

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)

        result = rf_mgr.click_info_icon()

        assert result is True
        mock_icon.click.assert_called_once()

    def test_click_info_icon_not_found(self):
        """Test clicking info icon when not present."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_iframe.locator.return_value.first.wait_for.side_effect = Exception("Not found")
        mock_page_mgr.get_rf_iframe.return_value = mock_iframe

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)

        result = rf_mgr.click_info_icon()

        assert result is False


class TestRFMenuManagerHelpers:
    """Test suite for helper methods."""

    def test_home_menu_has_hash_true(self):
        """Test detecting hash in home menu."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_iframe.locator.return_value.inner_text.return_value = "Menu #123"

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)

        result = rf_mgr._home_menu_has_hash(mock_iframe)

        assert result is True

    def test_home_menu_has_hash_false(self):
        """Test hash not in home menu."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        mock_iframe = MagicMock()
        mock_iframe.locator.return_value.inner_text.return_value = "Menu without hash"

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)

        result = rf_mgr._home_menu_has_hash(mock_iframe)

        assert result is False

    def test_slugify_for_filename(self):
        """Test slugifying text for filename."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)

        result = rf_mgr._slugify_for_filename("Test: Special@Characters!")

        assert result == "Test_Special_Characters"

    def test_slugify_for_filename_empty(self):
        """Test slugifying empty text."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)

        result = rf_mgr._slugify_for_filename("")

        assert result == "response"

    def test_slugify_for_filename_max_length(self):
        """Test slugifying with max length."""
        mock_page = MagicMock()
        mock_page_mgr = MagicMock()
        mock_screenshot = MagicMock()

        rf_mgr = RFMenuManager(mock_page, mock_page_mgr, mock_screenshot)

        long_text = "A" * 100
        result = rf_mgr._slugify_for_filename(long_text, max_len=50)

        assert len(result) <= 50


@pytest.mark.integration
class TestRFMenuManagerIntegration:
    """Integration tests for RFMenuManager."""

    def test_full_rf_navigation_flow(self):
        """Test complete RF navigation workflow."""
        # Placeholder for integration test
        pass

    def test_rf_error_handling_flow(self):
        """Test RF error handling workflow."""
        # Placeholder for integration test
        pass
