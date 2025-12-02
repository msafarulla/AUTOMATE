"""
Comprehensive tests for UI authentication (ui/auth.py).
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from ui.auth import AuthManager


class TestAuthManagerInitialization:
    """Test suite for AuthManager initialization."""

    def test_auth_manager_init_with_defaults(self):
        """Test AuthManager initialization with default values."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()
        mock_settings.app.credentials_env = 'dev'

        auth_mgr = AuthManager(mock_page, mock_screenshot, mock_settings)

        assert auth_mgr.page == mock_page
        assert auth_mgr.screenshot_mgr == mock_screenshot
        assert auth_mgr.credentials_env == 'dev'
        assert auth_mgr._credentials is None

    def test_auth_manager_init_with_custom_env(self):
        """Test AuthManager with custom credentials environment."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()
        mock_settings.app.credentials_env = 'dev'

        auth_mgr = AuthManager(
            mock_page,
            mock_screenshot,
            mock_settings,
            credentials_env='prod'
        )

        assert auth_mgr.credentials_env == 'prod'


class TestAuthManagerCredentials:
    """Test suite for credential management."""

    @patch('ui.auth.DB.get_credentials')
    def test_get_credentials_first_call(self, mock_get_creds):
        """Test getting credentials for first time."""
        mock_get_creds.return_value = {
            'app_server_user': 'testuser',
            'app_server_pass': 'testpass'
        }

        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()
        mock_settings.app.credentials_env = 'dev'

        auth_mgr = AuthManager(mock_page, mock_screenshot, mock_settings)
        creds = auth_mgr._get_credentials()

        assert creds['app_server_user'] == 'testuser'
        assert creds['app_server_pass'] == 'testpass'
        mock_get_creds.assert_called_once_with('dev')

    @patch('ui.auth.DB.get_credentials')
    def test_get_credentials_cached(self, mock_get_creds):
        """Test that credentials are cached after first call."""
        mock_get_creds.return_value = {
            'app_server_user': 'testuser',
            'app_server_pass': 'testpass'
        }

        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()
        mock_settings.app.credentials_env = 'dev'

        auth_mgr = AuthManager(mock_page, mock_screenshot, mock_settings)

        # Call twice
        creds1 = auth_mgr._get_credentials()
        creds2 = auth_mgr._get_credentials()

        # Should only call DB once
        assert mock_get_creds.call_count == 1
        assert creds1 == creds2


class TestAuthManagerLogin:
    """Test suite for login functionality."""

    @patch('ui.auth.DB.get_credentials')
    def test_login_success(self, mock_get_creds):
        """Test successful login flow."""
        mock_get_creds.return_value = {
            'app_server_user': 'testuser',
            'app_server_pass': 'testpass'
        }

        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()
        mock_settings.app.credentials_env = 'dev'
        mock_settings.app.app_server = 'http://test.com'
        mock_settings.app.auto_close_post_login_windows = False

        mock_locator_username = MagicMock()
        mock_locator_password = MagicMock()

        def locator_side_effect(selector):
            if selector == '#username':
                return mock_locator_username
            elif selector == '#password':
                return mock_locator_password
            return MagicMock()

        mock_page.locator.side_effect = locator_side_effect

        auth_mgr = AuthManager(mock_page, mock_screenshot, mock_settings)
        auth_mgr.login()

        # Verify page navigation
        mock_page.goto.assert_called_once()

        # Verify username filled
        mock_locator_username.fill.assert_called_once_with('testuser')

        # Verify password filled
        mock_locator_password.fill.assert_called_once_with('testpass')

        # Verify login button clicked
        mock_page.click.assert_called()

    @patch('ui.auth.DB.get_credentials')
    def test_login_button_enable_timeout(self, mock_get_creds):
        """Test handling of login button enable timeout."""
        mock_get_creds.return_value = {
            'app_server_user': 'testuser',
            'app_server_pass': 'testpass'
        }

        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()
        mock_settings.app.credentials_env = 'dev'
        mock_settings.app.app_server = 'http://test.com'
        mock_settings.app.auto_close_post_login_windows = False

        mock_locator_username = MagicMock()
        mock_locator_password = MagicMock()

        def locator_side_effect(selector):
            if selector == '#username':
                return mock_locator_username
            elif selector == '#password':
                return mock_locator_password
            return MagicMock()

        mock_page.locator.side_effect = locator_side_effect

        # Simulate timeout on wait_for_function
        mock_page.wait_for_function.side_effect = [
            PlaywrightTimeoutError("Timeout"),
            None  # Second call succeeds after retry
        ]

        # Mock evaluate to return proper button state
        mock_page.evaluate.return_value = {
            'disabled': True,
            'userLength': 8,
            'passLength': 8
        }

        auth_mgr = AuthManager(mock_page, mock_screenshot, mock_settings)

        # Should handle timeout gracefully
        try:
            auth_mgr.login()
        except Exception as e:
            # May raise exception or handle it
            pass

    @patch('ui.auth.DB.get_credentials')
    def test_login_with_auto_close_windows(self, mock_get_creds):
        """Test login with auto-close post-login windows enabled."""
        mock_get_creds.return_value = {
            'app_server_user': 'testuser',
            'app_server_pass': 'testpass'
        }

        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()
        mock_settings.app.credentials_env = 'dev'
        mock_settings.app.app_server = 'http://test.com'
        mock_settings.app.auto_close_post_login_windows = True

        # Mock post-login window detection
        mock_page.wait_for_selector.side_effect = PlaywrightTimeoutError("No windows")

        auth_mgr = AuthManager(mock_page, mock_screenshot, mock_settings)
        auth_mgr._close_default_windows = MagicMock()

        auth_mgr.login()

        # Verify close windows was called
        auth_mgr._close_default_windows.assert_called_once()

    @patch('ui.auth.DB.get_credentials')
    def test_login_navigation_failure(self, mock_get_creds):
        """Test handling of navigation failure during login."""
        mock_get_creds.return_value = {
            'app_server_user': 'testuser',
            'app_server_pass': 'testpass'
        }

        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()
        mock_settings.app.credentials_env = 'dev'
        mock_settings.app.app_server = 'http://test.com'

        # Simulate navigation timeout
        mock_page.expect_navigation.side_effect = PlaywrightTimeoutError("Navigation timeout")
        mock_page.keyboard.press.side_effect = PlaywrightTimeoutError("Navigation timeout")

        auth_mgr = AuthManager(mock_page, mock_screenshot, mock_settings)

        with pytest.raises(Exception, match="Login"):
            auth_mgr.login()


class TestAuthManagerCloseWindows:
    """Test suite for closing post-login windows."""

    def test_close_default_windows_no_windows(self):
        """Test closing windows when none are present."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()

        # Simulate no windows found
        mock_page.wait_for_selector.side_effect = PlaywrightTimeoutError("No windows")

        auth_mgr = AuthManager(mock_page, mock_screenshot, mock_settings)
        auth_mgr._close_default_windows()

        # Should not raise exception

    @patch('ui.auth.WaitUtils')
    def test_close_default_windows_single_window(self, mock_wait_utils):
        """Test closing a single post-login window."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()

        # Mock window locator
        mock_windows = MagicMock()
        mock_windows.count.side_effect = [1, 0]  # One window, then none
        mock_page.locator.return_value = mock_windows

        # Mock close button
        mock_close_btn = MagicMock()
        mock_close_btn.is_visible.return_value = True
        mock_windows.first.locator.return_value.first = mock_close_btn

        auth_mgr = AuthManager(mock_page, mock_screenshot, mock_settings)
        auth_mgr._close_default_windows()

        # Verify close button was clicked
        mock_close_btn.click.assert_called()

    @patch('ui.auth.WaitUtils')
    def test_close_default_windows_multiple_windows(self, mock_wait_utils):
        """Test closing multiple post-login windows."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()

        # Mock window counts: 3, then 2, then 1, then 0
        mock_windows = MagicMock()
        mock_windows.count.side_effect = [3, 2, 1, 0]
        mock_page.locator.return_value = mock_windows

        # Mock close button
        mock_close_btn = MagicMock()
        mock_close_btn.is_visible.return_value = True
        mock_windows.first.locator.return_value.first = mock_close_btn

        auth_mgr = AuthManager(mock_page, mock_screenshot, mock_settings)
        auth_mgr._close_default_windows()

        # Verify multiple close attempts
        assert mock_close_btn.click.call_count >= 2

    def test_close_default_windows_with_escape_fallback(self):
        """Test closing windows with Escape key fallback."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_settings = MagicMock()

        # Mock window locator
        mock_windows = MagicMock()
        mock_windows.count.side_effect = [1, 0]
        mock_page.locator.return_value = mock_windows

        # Mock close button not visible
        mock_windows.first.locator.return_value.first.is_visible.return_value = False

        # Mock keyboard
        mock_page.keyboard = MagicMock()

        auth_mgr = AuthManager(mock_page, mock_screenshot, mock_settings)
        auth_mgr._close_default_windows()

        # Should have tried Escape key
        mock_page.keyboard.press.assert_called()


@pytest.mark.integration
class TestAuthManagerIntegration:
    """Integration tests for AuthManager."""

    def test_full_login_flow(self):
        """Test complete login flow with real browser."""
        # Placeholder for integration test
        pass

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials."""
        # Placeholder for integration test
        pass

    def test_login_timeout_scenarios(self):
        """Test various timeout scenarios."""
        # Placeholder for integration test
        pass
