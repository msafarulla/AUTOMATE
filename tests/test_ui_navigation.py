"""
Comprehensive tests for UI navigation (ui/navigation.py).
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from ui.navigation import NavigationManager


class TestNavigationManagerInitialization:
    """Test suite for NavigationManager initialization."""

    def test_navigation_manager_init(self):
        """Test NavigationManager initialization."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        nav_mgr = NavigationManager(mock_page, mock_screenshot)

        assert nav_mgr.page == mock_page
        assert nav_mgr.screenshot_mgr == mock_screenshot


class TestNavigationManagerChangeWarehouse:
    """Test suite for warehouse change functionality."""

    @patch('ui.navigation.WaitUtils')
    @patch('ui.navigation.HashUtils')
    def test_change_warehouse_already_selected(self, mock_hash, mock_wait):
        """Test changing warehouse when already in target warehouse."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        # Mock current warehouse display
        mock_locator = MagicMock()
        mock_locator.inner_text.return_value = "LPM - SOA"
        mock_page.locator.return_value.first = mock_locator

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr.change_warehouse("LPM")

        # Should not try to change if already selected
        mock_page.locator.return_value.first.click.assert_not_called()

    @patch('ui.navigation.WaitUtils')
    @patch('ui.navigation.HashUtils')
    def test_change_warehouse_success(self, mock_hash, mock_wait):
        """Test successful warehouse change."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        # Mock current warehouse
        mock_current = MagicMock()
        mock_current.inner_text.return_value = "ABC - SOA"

        # Mock dropdown selection
        mock_page.locator.return_value.first = mock_current

        # Mock hash for screen change detection
        mock_hash.get_frame_snapshot.return_value = "snapshot1"
        mock_wait.wait_for_screen_change.return_value = True

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr.change_warehouse("LPM", onDemand=False)

        # Verify warehouse selection process
        mock_current.click.assert_called()
        mock_screenshot.capture.assert_called()

    @patch('ui.navigation.WaitUtils')
    @patch('ui.navigation.HashUtils')
    def test_change_warehouse_case_insensitive(self, mock_hash, mock_wait):
        """Test warehouse change is case insensitive."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        mock_locator = MagicMock()
        mock_locator.inner_text.return_value = "lpm - SOA"
        mock_page.locator.return_value.first = mock_locator

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr.change_warehouse("LPM")

        # Should recognize as already selected (case insensitive)
        mock_locator.click.assert_not_called()


class TestNavigationManagerOpenMenuItem:
    """Test suite for opening menu items."""

    def test_open_menu_item_no_results(self):
        """Test opening menu item when search returns no results."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        # Mock empty search results
        mock_items = MagicMock()
        mock_page.locator.return_value = mock_items

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr._open_menu_panel = MagicMock()
        nav_mgr._reset_menu_filter = MagicMock()
        nav_mgr._do_search = MagicMock()
        nav_mgr._wait_for_results = MagicMock(return_value=0)
        nav_mgr.close_active_windows = MagicMock()

        result = nav_mgr.open_menu_item("NonExistent", "NonExistent")

        assert result is False

    def test_open_menu_item_success(self):
        """Test successfully opening a menu item."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        # Mock search results
        mock_items = MagicMock()
        mock_item = MagicMock()
        mock_item.inner_text.return_value = "Test Menu"
        mock_items.nth.return_value = mock_item
        mock_page.locator.return_value = mock_items

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr._open_menu_panel = MagicMock()
        nav_mgr._reset_menu_filter = MagicMock()
        nav_mgr._do_search = MagicMock()
        nav_mgr._wait_for_results = MagicMock(return_value=1)
        nav_mgr._click_menu_item = MagicMock()
        nav_mgr._wait_for_window_ready = MagicMock()
        nav_mgr._post_selection_adjustments = MagicMock()
        nav_mgr._maximize_with_wait = MagicMock()
        nav_mgr.close_active_windows = MagicMock()

        result = nav_mgr.open_menu_item("Test", "Test Menu", onDemand=False)

        assert result is True
        nav_mgr._click_menu_item.assert_called_once()

    def test_open_menu_item_rf_menu(self):
        """Test opening RF Menu (special case)."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        mock_items = MagicMock()
        mock_item = MagicMock()
        mock_item.inner_text.return_value = "RF Menu"
        mock_items.nth.return_value = mock_item
        mock_page.locator.return_value = mock_items

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr._open_menu_panel = MagicMock()
        nav_mgr._reset_menu_filter = MagicMock()
        nav_mgr._do_search = MagicMock()
        nav_mgr._wait_for_results = MagicMock(return_value=1)
        nav_mgr._click_menu_item = MagicMock()
        nav_mgr._wait_for_window_ready = MagicMock()
        nav_mgr._post_selection_adjustments = MagicMock()
        nav_mgr.maximize_rf_window = MagicMock()
        nav_mgr.close_active_windows = MagicMock()

        result = nav_mgr.open_menu_item("RF", "RF Menu", onDemand=False)

        # Should call maximize_rf_window for RF Menu
        nav_mgr.maximize_rf_window.assert_called()

    def test_open_menu_item_no_exact_match(self):
        """Test when no exact match is found."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        mock_items = MagicMock()
        mock_item = MagicMock()
        mock_item.inner_text.return_value = "Similar But Not Exact"
        mock_items.nth.return_value = mock_item
        mock_page.locator.return_value = mock_items

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr._open_menu_panel = MagicMock()
        nav_mgr._reset_menu_filter = MagicMock()
        nav_mgr._do_search = MagicMock()
        nav_mgr._wait_for_results = MagicMock(return_value=1)
        nav_mgr.close_active_windows = MagicMock()

        result = nav_mgr.open_menu_item("Test", "Exact Match", onDemand=False)

        assert result is False


class TestNavigationManagerWindowManagement:
    """Test suite for window management."""

    def test_close_active_windows_no_windows(self):
        """Test closing windows when none exist."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr._find_closeable_window = MagicMock(return_value=None)

        nav_mgr.close_active_windows()

        # Should not crash when no windows exist

    @patch('ui.navigation.WaitUtils')
    def test_close_active_windows_single_window(self, mock_wait):
        """Test closing a single window."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        mock_window = MagicMock()
        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr._find_closeable_window = MagicMock(side_effect=[mock_window, None])
        nav_mgr._get_title = MagicMock(return_value="Test Window")
        nav_mgr._close_window = MagicMock(return_value=True)

        nav_mgr.close_active_windows()

        nav_mgr._close_window.assert_called_once_with(mock_window)

    def test_close_active_windows_with_skip_list(self):
        """Test closing windows with skip list."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr._find_closeable_window = MagicMock(return_value=None)

        nav_mgr.close_active_windows(skip_titles=["RF Menu", "Important"])

        # Should pass skip list to find_closeable_window
        nav_mgr._find_closeable_window.assert_called()

    def test_focus_window_by_title_found(self):
        """Test focusing window by title when found."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        mock_window = MagicMock()
        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr._get_visible_windows = MagicMock(return_value=[mock_window])
        nav_mgr._get_title = MagicMock(return_value="Test Window")

        result = nav_mgr.focus_window_by_title("Test")

        assert result is True
        mock_window.evaluate.assert_called()

    def test_focus_window_by_title_not_found(self):
        """Test focusing window by title when not found."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr._get_visible_windows = MagicMock(return_value=[])

        result = nav_mgr.focus_window_by_title("NonExistent")

        assert result is False


class TestNavigationManagerMaximize:
    """Test suite for window maximize functionality."""

    @patch('ui.navigation.safe_page_evaluate')
    def test_maximize_non_rf_windows(self, mock_evaluate):
        """Test maximizing non-RF windows."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        mock_evaluate.return_value = 2  # 2 windows maximized

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        nav_mgr._maximize_non_rf_windows()

        # Should call page evaluate for ExtJS maximize
        assert mock_evaluate.called

    def test_maximize_rf_window(self):
        """Test maximizing RF Menu window."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        mock_rf_window = MagicMock()
        mock_page.locator.return_value.last = mock_rf_window

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        result = nav_mgr.maximize_rf_window()

        assert result is True
        mock_rf_window.evaluate.assert_called()

    def test_maximize_rf_window_not_found(self):
        """Test maximizing RF window when not found."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        mock_page.locator.return_value.last.wait_for.side_effect = Exception("Not found")

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        result = nav_mgr.maximize_rf_window()

        assert result is False


class TestNavigationManagerHelpers:
    """Test suite for helper methods."""

    def test_normalize_text(self):
        """Test text normalization."""
        result = NavigationManager._normalize("Test  Multiple   Spaces")
        assert result == "test multiple spaces"

    def test_normalize_text_with_nbsp(self):
        """Test normalizing text with non-breaking spaces."""
        text_with_nbsp = "Test\xa0with\xa0nbsp"
        result = NavigationManager._normalize(text_with_nbsp)
        assert result == "test with nbsp"

    def test_normalize_text_with_newlines(self):
        """Test normalizing text with newlines."""
        result = NavigationManager._normalize("Test\nWith\nNewlines")
        assert result == "test with newlines"

    def test_get_visible_windows(self):
        """Test getting visible windows."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        mock_windows = MagicMock()
        mock_windows.count.return_value = 2
        mock_page.locator.return_value = mock_windows

        nav_mgr = NavigationManager(mock_page, mock_screenshot)
        windows = nav_mgr._get_visible_windows()

        assert len(windows) == 2


@pytest.mark.integration
class TestNavigationManagerIntegration:
    """Integration tests for NavigationManager."""

    def test_full_navigation_flow(self):
        """Test complete navigation workflow."""
        # Placeholder for integration test
        pass

    def test_multiple_window_operations(self):
        """Test multiple window open/close operations."""
        # Placeholder for integration test
        pass
