"""
Tests for BrowserManager class.
"""
import pytest
from unittest.mock import MagicMock, patch, call

from core.browser import BrowserManager
from config.settings import Settings, BrowserConfig


class TestBrowserManagerInitialization:
    """Tests for BrowserManager initialization."""

    def test_init_with_default_settings(self):
        """Test initialization with default settings."""
        with patch('core.browser.Settings') as mock_settings_class:
            mock_settings = MagicMock()
            mock_settings_class.return_value = mock_settings

            mgr = BrowserManager()

            assert mgr.playwright is None
            assert mgr.browser is None
            assert mgr.context is None
            # Should create default settings
            mock_settings_class.assert_called_once()

    def test_init_with_provided_settings(self):
        """Test initialization with provided settings."""
        mock_settings = MagicMock(spec=Settings)

        mgr = BrowserManager(settings=mock_settings)

        assert mgr.settings is mock_settings
        assert mgr.playwright is None
        assert mgr.browser is None
        assert mgr.context is None


class TestContextManager:
    """Tests for context manager methods (__enter__ and __exit__)."""

    @patch('core.browser.sync_playwright')
    def test_enter_starts_playwright_and_creates_browser_and_context(self, mock_sync_playwright):
        """Test __enter__ starts playwright and creates browser and context."""
        # Setup mocks
        mock_playwright_instance = MagicMock()
        mock_playwright_starter = MagicMock()
        mock_playwright_starter.start.return_value = mock_playwright_instance
        mock_sync_playwright.return_value = mock_playwright_starter

        mock_browser = MagicMock()
        mock_context = MagicMock()

        mock_settings = MagicMock(spec=Settings)
        mock_settings.browser = MagicMock(
            width=1920,
            height=1080,
            device_scale_factor=1.0,
            headless=False
        )

        mgr = BrowserManager(settings=mock_settings)
        mgr._create_browser = MagicMock(return_value=mock_browser)
        mgr._create_context = MagicMock(return_value=mock_context)

        result = mgr.__enter__()

        # Verify playwright was started
        mock_sync_playwright.assert_called_once()
        mock_playwright_starter.start.assert_called_once()
        assert mgr.playwright is mock_playwright_instance

        # Verify browser was created
        mgr._create_browser.assert_called_once()
        assert mgr.browser is mock_browser

        # Verify context was created
        mgr._create_context.assert_called_once()
        assert mgr.context is mock_context

        # Verify returns self
        assert result is mgr

    def test_exit_closes_context_browser_and_stops_playwright(self):
        """Test __exit__ closes all resources."""
        mock_context = MagicMock()
        mock_browser = MagicMock()
        mock_playwright = MagicMock()

        mock_settings = MagicMock(spec=Settings)
        mgr = BrowserManager(settings=mock_settings)
        mgr.context = mock_context
        mgr.browser = mock_browser
        mgr.playwright = mock_playwright

        mgr.__exit__(None, None, None)

        # Verify resources were closed in order
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()

    def test_exit_handles_missing_context(self):
        """Test __exit__ handles missing context gracefully."""
        mock_browser = MagicMock()
        mock_playwright = MagicMock()

        mock_settings = MagicMock(spec=Settings)
        mgr = BrowserManager(settings=mock_settings)
        mgr.context = None
        mgr.browser = mock_browser
        mgr.playwright = mock_playwright

        mgr.__exit__(None, None, None)

        # Browser and playwright should still be closed
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()

    def test_exit_handles_missing_browser(self):
        """Test __exit__ handles missing browser gracefully."""
        mock_context = MagicMock()
        mock_playwright = MagicMock()

        mock_settings = MagicMock(spec=Settings)
        mgr = BrowserManager(settings=mock_settings)
        mgr.context = mock_context
        mgr.browser = None
        mgr.playwright = mock_playwright

        mgr.__exit__(None, None, None)

        # Context and playwright should still be closed
        mock_context.close.assert_called_once()
        mock_playwright.stop.assert_called_once()

    def test_exit_handles_missing_playwright(self):
        """Test __exit__ handles missing playwright gracefully."""
        mock_context = MagicMock()
        mock_browser = MagicMock()

        mock_settings = MagicMock(spec=Settings)
        mgr = BrowserManager(settings=mock_settings)
        mgr.context = mock_context
        mgr.browser = mock_browser
        mgr.playwright = None

        mgr.__exit__(None, None, None)

        # Context and browser should still be closed
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()


class TestCreateBrowser:
    """Tests for _create_browser method."""

    def test_creates_browser_with_correct_launch_args(self):
        """Test creates browser with correct launch arguments."""
        mock_playwright = MagicMock()
        mock_chromium = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.chromium = mock_chromium
        mock_chromium.launch.return_value = mock_browser

        mock_settings = MagicMock(spec=Settings)
        mock_settings.browser = MagicMock(
            width=1920,
            height=1080,
            device_scale_factor=1.0,
            headless=False
        )

        mgr = BrowserManager(settings=mock_settings)
        mgr.playwright = mock_playwright

        result = mgr._create_browser()

        # Verify launch was called with correct arguments
        mock_chromium.launch.assert_called_once()
        call_kwargs = mock_chromium.launch.call_args[1]

        assert call_kwargs['headless'] is False
        assert '--start-fullscreen' in call_kwargs['args']
        assert '--window-size=1920,1080' in call_kwargs['args']
        assert '--ignore-certificate-errors' in call_kwargs['args']
        assert '--disable-blink-features=AutomationControlled' in call_kwargs['args']

        assert result is mock_browser

    def test_creates_browser_with_headless_mode(self):
        """Test creates browser with headless mode enabled."""
        mock_playwright = MagicMock()
        mock_chromium = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.chromium = mock_chromium
        mock_chromium.launch.return_value = mock_browser

        mock_settings = MagicMock(spec=Settings)
        mock_settings.browser = MagicMock(
            width=1920,
            height=1080,
            device_scale_factor=1.0,
            headless=True
        )

        mgr = BrowserManager(settings=mock_settings)
        mgr.playwright = mock_playwright

        result = mgr._create_browser()

        # Verify headless is True
        call_kwargs = mock_chromium.launch.call_args[1]
        assert call_kwargs['headless'] is True

    def test_calculates_window_size_with_scale_factor(self):
        """Test calculates window size correctly with scale factor."""
        mock_playwright = MagicMock()
        mock_chromium = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.chromium = mock_chromium
        mock_chromium.launch.return_value = mock_browser

        mock_settings = MagicMock(spec=Settings)
        mock_settings.browser = MagicMock(
            width=3840,
            height=2160,
            device_scale_factor=2.0,
            headless=False
        )

        mgr = BrowserManager(settings=mock_settings)
        mgr.playwright = mock_playwright

        result = mgr._create_browser()

        # Window size should be divided by scale factor
        # 3840/2 = 1920, 2160/2 = 1080
        call_kwargs = mock_chromium.launch.call_args[1]
        assert '--window-size=1920,1080' in call_kwargs['args']

    def test_ensures_minimum_scale_factor_of_one(self):
        """Test ensures minimum scale factor of 1.0."""
        mock_playwright = MagicMock()
        mock_chromium = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.chromium = mock_chromium
        mock_chromium.launch.return_value = mock_browser

        mock_settings = MagicMock(spec=Settings)
        mock_settings.browser = MagicMock(
            width=1920,
            height=1080,
            device_scale_factor=0.5,  # Less than 1.0
            headless=False
        )

        mgr = BrowserManager(settings=mock_settings)
        mgr.playwright = mock_playwright

        result = mgr._create_browser()

        # Should use 1.0 as minimum, so no division
        call_kwargs = mock_chromium.launch.call_args[1]
        assert '--window-size=1920,1080' in call_kwargs['args']


class TestCreateContext:
    """Tests for _create_context method."""

    def test_creates_context_with_correct_viewport(self):
        """Test creates context with correct viewport settings."""
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_settings = MagicMock(spec=Settings)
        mock_settings.browser = MagicMock(
            width=1920,
            height=1080,
            device_scale_factor=1.0,
            headless=False
        )

        mgr = BrowserManager(settings=mock_settings)
        mgr.browser = mock_browser

        with patch('core.browser.app_log'):
            result = mgr._create_context()

        # Viewport height should be height - 300
        # 1080 - 300 = 780
        mock_browser.new_context.assert_called_once()
        call_kwargs = mock_browser.new_context.call_args[1]

        assert call_kwargs['viewport']['width'] == 1920
        assert call_kwargs['viewport']['height'] == 780
        assert call_kwargs['device_scale_factor'] == 1.0
        assert call_kwargs['ignore_https_errors'] is True

        assert result is mock_context

    def test_creates_context_with_scale_factor(self):
        """Test creates context with scale factor applied to viewport."""
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_settings = MagicMock(spec=Settings)
        mock_settings.browser = MagicMock(
            width=3840,
            height=2160,
            device_scale_factor=2.0,
            headless=False
        )

        mgr = BrowserManager(settings=mock_settings)
        mgr.browser = mock_browser

        with patch('core.browser.app_log'):
            result = mgr._create_context()

        # Viewport should be divided by scale factor
        # width: 3840/2 = 1920
        # height: (2160-300)/2 = 930
        call_kwargs = mock_browser.new_context.call_args[1]

        assert call_kwargs['viewport']['width'] == 1920
        assert call_kwargs['viewport']['height'] == 930
        assert call_kwargs['device_scale_factor'] == 2.0

    def test_logs_viewport_information(self):
        """Test logs viewport information."""
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_settings = MagicMock(spec=Settings)
        mock_settings.browser = MagicMock(
            width=1920,
            height=1080,
            device_scale_factor=1.5,
            headless=False
        )

        mgr = BrowserManager(settings=mock_settings)
        mgr.browser = mock_browser

        with patch('core.browser.app_log') as mock_log:
            result = mgr._create_context()

            mock_log.assert_called_once()
            log_message = mock_log.call_args[0][0]
            assert 'viewport=' in log_message
            assert 'raw=' in log_message
            assert 'scale=' in log_message


class TestNewContext:
    """Tests for new_context method."""

    def test_creates_additional_context_with_same_settings(self):
        """Test creates additional context with same viewport settings."""
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_settings = MagicMock(spec=Settings)
        mock_settings.browser = MagicMock(
            width=1920,
            height=1080,
            device_scale_factor=1.0,
            headless=False
        )

        mgr = BrowserManager(settings=mock_settings)
        mgr.browser = mock_browser

        result = mgr.new_context()

        # Should create context with same viewport settings
        mock_browser.new_context.assert_called_once()
        call_kwargs = mock_browser.new_context.call_args[1]

        assert call_kwargs['viewport']['width'] == 1920
        assert call_kwargs['viewport']['height'] == 780  # 1080 - 300
        assert call_kwargs['device_scale_factor'] == 1.0
        assert call_kwargs['ignore_https_errors'] is True

        assert result is mock_context

    def test_creates_context_with_scale_factor_applied(self):
        """Test new_context applies scale factor correctly."""
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_settings = MagicMock(spec=Settings)
        mock_settings.browser = MagicMock(
            width=2560,
            height=1440,
            device_scale_factor=2.0,
            headless=False
        )

        mgr = BrowserManager(settings=mock_settings)
        mgr.browser = mock_browser

        result = mgr.new_context()

        # Viewport should be divided by scale factor
        # width: 2560/2 = 1280
        # height: (1440-300)/2 = 570
        call_kwargs = mock_browser.new_context.call_args[1]

        assert call_kwargs['viewport']['width'] == 1280
        assert call_kwargs['viewport']['height'] == 570
        assert call_kwargs['device_scale_factor'] == 2.0


class TestNewPage:
    """Tests for new_page method."""

    def test_creates_new_page_from_context(self):
        """Test creates new page from browser context."""
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_settings = MagicMock(spec=Settings)
        mgr = BrowserManager(settings=mock_settings)
        mgr.context = mock_context

        result = mgr.new_page()

        mock_context.new_page.assert_called_once()
        assert result is mock_page


class TestIntegration:
    """Integration tests for BrowserManager."""

    @patch('core.browser.sync_playwright')
    @patch('core.browser.app_log')
    def test_full_context_manager_lifecycle(self, mock_log, mock_sync_playwright):
        """Test full lifecycle using context manager."""
        # Setup complete mock chain
        mock_playwright_instance = MagicMock()
        mock_playwright_starter = MagicMock()
        mock_playwright_starter.start.return_value = mock_playwright_instance
        mock_sync_playwright.return_value = mock_playwright_starter

        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser
        mock_playwright_instance.chromium = mock_chromium

        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_settings = MagicMock(spec=Settings)
        mock_settings.browser = MagicMock(
            width=1920,
            height=1080,
            device_scale_factor=1.0,
            headless=False
        )

        # Use context manager
        with BrowserManager(settings=mock_settings) as mgr:
            # Verify initialization
            assert mgr.playwright is mock_playwright_instance
            assert mgr.browser is mock_browser
            assert mgr.context is mock_context

            # Create a page
            page = mgr.new_page()
            assert page is mock_page

            # Create additional context
            new_ctx = mgr.new_context()
            assert new_ctx is mock_context

        # Verify cleanup happened
        mock_context.close.assert_called()
        mock_browser.close.assert_called_once()
        mock_playwright_instance.stop.assert_called_once()

    @patch('core.browser.sync_playwright')
    @patch('core.browser.app_log')
    def test_viewport_calculations_with_various_scales(self, mock_log, mock_sync_playwright):
        """Test viewport calculations work correctly with different scale factors."""
        # Setup mocks
        mock_playwright_instance = MagicMock()
        mock_playwright_starter = MagicMock()
        mock_playwright_starter.start.return_value = mock_playwright_instance
        mock_sync_playwright.return_value = mock_playwright_starter

        mock_browser = MagicMock()
        mock_context = MagicMock()

        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser
        mock_playwright_instance.chromium = mock_chromium

        mock_browser.new_context.return_value = mock_context

        test_cases = [
            (1920, 1080, 1.0, 1920, 780),   # Scale 1.0
            (3840, 2160, 2.0, 1920, 930),   # Scale 2.0
            (2560, 1440, 1.5, 1706, 760),   # Scale 1.5
        ]

        for width, height, scale, expected_vp_width, expected_vp_height in test_cases:
            mock_settings = MagicMock(spec=Settings)
            mock_settings.browser = MagicMock(
                width=width,
                height=height,
                device_scale_factor=scale,
                headless=False
            )

            with BrowserManager(settings=mock_settings) as mgr:
                # Check context was created with correct viewport
                call_kwargs = mock_browser.new_context.call_args[1]
                assert call_kwargs['viewport']['width'] == expected_vp_width
                assert call_kwargs['viewport']['height'] == expected_vp_height
                assert call_kwargs['device_scale_factor'] == scale

            # Reset mock for next iteration
            mock_browser.new_context.reset_mock()
