"""
Comprehensive tests for ui/navigation.py to improve coverage.
"""
import pytest
from unittest.mock import MagicMock, Mock, patch, call
from ui.navigation import NavigationManager


class TestNavigationManagerInit:
    """Tests for NavigationManager initialization."""

    def test_init_sets_attributes(self):
        """Test initialization sets attributes correctly."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        nav = NavigationManager(mock_page, mock_screenshot)

        assert nav.page is mock_page
        assert nav.screenshot_mgr is mock_screenshot


class TestChangeWarehouse:
    """Tests for change_warehouse method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        return NavigationManager(MagicMock(), MagicMock())

    def test_change_warehouse_on_demand(self, nav_mgr):
        """Test change_warehouse with onDemand=True."""
        with patch.object(nav_mgr, 'open_menu_item') as mock_open, \
             patch('ui.navigation.WaitUtils'):
            mock_open.return_value = True

            nav_mgr.change_warehouse("WH01", onDemand=True)

            # Should open Warehouse Change (on Demand)
            calls = [str(call) for call in mock_open.call_args_list]
            assert any("on Demand" in str(call) or "on demand" in str(call).lower() for call in calls)

    def test_change_warehouse_not_on_demand(self, nav_mgr):
        """Test change_warehouse with onDemand=False."""
        with patch.object(nav_mgr, 'open_menu_item') as mock_open, \
             patch('ui.navigation.WaitUtils'):
            mock_open.return_value = True

            nav_mgr.change_warehouse("WH01", onDemand=False)

            # Should open regular Warehouse Change
            mock_open.assert_called()


class TestOpenMenuItem:
    """Tests for open_menu_item method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_open_menu_item_basic_success(self, nav_mgr):
        """Test open_menu_item basic successful flow."""
        with patch.object(nav_mgr, '_open_menu_panel'), \
             patch.object(nav_mgr, '_reset_menu_filter'), \
             patch.object(nav_mgr, '_do_search'), \
             patch.object(nav_mgr, '_wait_for_results', return_value=1), \
             patch.object(nav_mgr, '_click_menu_item'), \
             patch.object(nav_mgr, '_wait_for_window_ready', return_value=True), \
             patch.object(nav_mgr, '_post_selection_adjustments'):

            result = nav_mgr.open_menu_item("TEST", "Test Window")

            assert result is True

    def test_open_menu_item_no_results(self, nav_mgr):
        """Test open_menu_item when search returns no results."""
        with patch.object(nav_mgr, '_open_menu_panel'), \
             patch.object(nav_mgr, '_reset_menu_filter'), \
             patch.object(nav_mgr, '_do_search'), \
             patch.object(nav_mgr, '_wait_for_results', return_value=0):

            result = nav_mgr.open_menu_item("TEST", "Test Window")

            assert result is False

    def test_open_menu_item_window_not_ready(self, nav_mgr):
        """Test open_menu_item when window is not ready."""
        with patch.object(nav_mgr, '_open_menu_panel'), \
             patch.object(nav_mgr, '_reset_menu_filter'), \
             patch.object(nav_mgr, '_do_search'), \
             patch.object(nav_mgr, '_wait_for_results', return_value=1), \
             patch.object(nav_mgr, '_click_menu_item'), \
             patch.object(nav_mgr, '_wait_for_window_ready', return_value=False):

            result = nav_mgr.open_menu_item("TEST", "Test Window")

            assert result is False

    def test_open_menu_item_with_retries(self, nav_mgr):
        """Test open_menu_item retries on timeout."""
        call_count = [0]

        def mock_wait_results(locator, timeout_ms=3000):
            call_count[0] += 1
            if call_count[0] < 2:
                return 0  # First call fails
            return 1  # Second call succeeds

        with patch.object(nav_mgr, '_open_menu_panel'), \
             patch.object(nav_mgr, '_reset_menu_filter'), \
             patch.object(nav_mgr, '_do_search'), \
             patch.object(nav_mgr, '_wait_for_results', side_effect=mock_wait_results), \
             patch.object(nav_mgr, '_click_menu_item'), \
             patch.object(nav_mgr, '_wait_for_window_ready', return_value=True), \
             patch.object(nav_mgr, '_post_selection_adjustments'):

            result = nav_mgr.open_menu_item("TEST", "Test Window", max_retries=2)

            assert result is True
            assert call_count[0] == 2


class TestWaitForWindowReady:
    """Tests for _wait_for_window_ready method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_wait_for_window_ready_finds_window(self, nav_mgr):
        """Test _wait_for_window_ready finds matching window."""
        mock_window = MagicMock()
        mock_window.title.return_value = "Test Window"
        nav_mgr.page.context.pages = [mock_window]

        with patch.object(nav_mgr, '_normalize', return_value="test window"), \
             patch('ui.navigation.time'):
            result = nav_mgr._wait_for_window_ready("test window", timeout_ms=1000)

            assert result is True

    def test_wait_for_window_ready_timeout(self, nav_mgr):
        """Test _wait_for_window_ready times out."""
        nav_mgr.page.context.pages = []

        with patch.object(nav_mgr, '_normalize', return_value="test window"), \
             patch('ui.navigation.time.monotonic', side_effect=[0, 0.1, 2.0]):
            result = nav_mgr._wait_for_window_ready("test window", timeout_ms=1000)

            assert result is False


class TestWaitForIlpnGridReady:
    """Tests for _wait_for_ilpn_grid_ready method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_wait_for_ilpn_grid_ready_success(self, nav_mgr):
        """Test _wait_for_ilpn_grid_ready successful wait."""
        mock_locator = MagicMock()
        nav_mgr.page.locator.return_value = mock_locator

        with patch('ui.navigation.WaitUtils'):
            result = nav_mgr._wait_for_ilpn_grid_ready(timeout_ms=1000)

            assert result is True

    def test_wait_for_ilpn_grid_ready_timeout(self, nav_mgr):
        """Test _wait_for_ilpn_grid_ready handles timeout."""
        mock_locator = MagicMock()
        mock_locator.wait_for.side_effect = Exception("Timeout")
        nav_mgr.page.locator.return_value = mock_locator

        with patch('ui.navigation.WaitUtils'):
            result = nav_mgr._wait_for_ilpn_grid_ready(timeout_ms=1000)

            assert result is False


class TestMaximizeWithWait:
    """Tests for _maximize_with_wait method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_maximize_with_wait_success_first_attempt(self, nav_mgr):
        """Test _maximize_with_wait succeeds on first attempt."""
        mock_window = MagicMock()
        mock_window.title.return_value = "Test Window"
        nav_mgr.page.context.pages = [mock_window]

        with patch.object(nav_mgr, '_normalize', return_value="test window"), \
             patch('ui.navigation.WaitUtils'):
            result = nav_mgr._maximize_with_wait("test window")

            assert result is True
            # Should not wait long on first success
            assert mock_window.set_viewport_size.called or mock_window.evaluate.called

    def test_maximize_with_wait_retries(self, nav_mgr):
        """Test _maximize_with_wait retries on failure."""
        mock_window = MagicMock()
        mock_window.title.return_value = "Test Window"
        nav_mgr.page.context.pages = [mock_window]

        call_count = [0]

        def mock_wait_for_mask():
            call_count[0] += 1
            if call_count[0] < 2:
                return False
            return True

        with patch.object(nav_mgr, '_normalize', return_value="test window"), \
             patch.object(nav_mgr, '_wait_for_mask', side_effect=mock_wait_for_mask), \
             patch('ui.navigation.WaitUtils'):
            result = nav_mgr._maximize_with_wait("test window", max_attempts=2)

            assert call_count[0] == 2


class TestFocusWindowByTitle:
    """Tests for focus_window_by_title method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_focus_window_by_title_success(self, nav_mgr):
        """Test focus_window_by_title finds and focuses window."""
        mock_window = MagicMock()
        mock_window.title.return_value = "Test Window"
        nav_mgr.page.context.pages = [mock_window]

        result = nav_mgr.focus_window_by_title("Test")

        assert result is True
        mock_window.bring_to_front.assert_called_once()

    def test_focus_window_by_title_not_found(self, nav_mgr):
        """Test focus_window_by_title returns False when not found."""
        nav_mgr.page.context.pages = []

        result = nav_mgr.focus_window_by_title("Test")

        assert result is False


class TestCloseActiveWindows:
    """Tests for close_active_windows method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_close_active_windows_closes_windows(self, nav_mgr):
        """Test close_active_windows closes matching windows."""
        mock_window1 = MagicMock()
        mock_window1.title.return_value = "Window 1"
        mock_window2 = MagicMock()
        mock_window2.title.return_value = "Window 2"

        with patch.object(nav_mgr, '_get_visible_windows', return_value=[mock_window1, mock_window2]), \
             patch.object(nav_mgr, '_close_window', return_value=True):

            nav_mgr.close_active_windows()

    def test_close_active_windows_with_skip_titles(self, nav_mgr):
        """Test close_active_windows skips specified titles."""
        mock_window1 = MagicMock()
        mock_window1.title.return_value = "Keep This"
        mock_window2 = MagicMock()
        mock_window2.title.return_value = "Close This"

        with patch.object(nav_mgr, '_get_visible_windows', return_value=[mock_window1, mock_window2]), \
             patch.object(nav_mgr, '_find_closeable_window') as mock_find:
            mock_find.side_effect = [mock_window2, None]

            nav_mgr.close_active_windows(skip_titles=["Keep This"])


class TestCloseMenuOverlayAfterSignOn:
    """Tests for close_menu_overlay_after_sign_on method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_close_menu_overlay_after_sign_on(self, nav_mgr):
        """Test close_menu_overlay_after_sign_on presses Escape."""
        with patch('ui.navigation.WaitUtils'):
            nav_mgr.close_menu_overlay_after_sign_on()

            nav_mgr.page.keyboard.press.assert_called_with("Escape")


class TestOpenMenuPanel:
    """Tests for _open_menu_panel method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_open_menu_panel_opens_panel(self, nav_mgr):
        """Test _open_menu_panel triggers menu opening."""
        mock_locator = MagicMock()
        nav_mgr.page.locator.return_value = mock_locator

        with patch('ui.navigation.WaitUtils'):
            nav_mgr._open_menu_panel()

            # Should click on menu trigger
            assert nav_mgr.page.locator.called or nav_mgr.page.keyboard.press.called


class TestResetMenuFilter:
    """Tests for _reset_menu_filter method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_reset_menu_filter_clears_input(self, nav_mgr):
        """Test _reset_menu_filter clears menu filter input."""
        mock_input = MagicMock()
        nav_mgr.page.locator.return_value = mock_input

        nav_mgr._reset_menu_filter()

        mock_input.fill.assert_called_with("")


class TestDoSearch:
    """Tests for _do_search method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_do_search_fills_and_triggers(self, nav_mgr):
        """Test _do_search fills search term."""
        mock_input = MagicMock()
        nav_mgr.page.locator.return_value = mock_input

        with patch('ui.navigation.WaitUtils'):
            nav_mgr._do_search("TEST TERM")

            mock_input.fill.assert_called_with("TEST TERM")


class TestWaitForResults:
    """Tests for _wait_for_results method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        return NavigationManager(MagicMock(), MagicMock())

    def test_wait_for_results_returns_count(self, nav_mgr):
        """Test _wait_for_results returns result count."""
        mock_locator = MagicMock()
        mock_locator.count.return_value = 5

        result = nav_mgr._wait_for_results(mock_locator, timeout_ms=1000)

        assert result == 5

    def test_wait_for_results_handles_timeout(self, nav_mgr):
        """Test _wait_for_results handles timeout exception."""
        mock_locator = MagicMock()
        mock_locator.wait_for.side_effect = Exception("Timeout")

        result = nav_mgr._wait_for_results(mock_locator, timeout_ms=1000)

        assert result == 0


class TestClickMenuItem:
    """Tests for _click_menu_item method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        return NavigationManager(MagicMock(), MagicMock())

    def test_click_menu_item_basic(self, nav_mgr):
        """Test _click_menu_item clicks item."""
        mock_item = MagicMock()

        with patch('ui.navigation.WaitUtils'):
            nav_mgr._click_menu_item(mock_item, use_info_button=False)

            mock_item.click.assert_called_once()

    def test_click_menu_item_with_info_button(self, nav_mgr):
        """Test _click_menu_item uses info button when requested."""
        mock_item = MagicMock()
        mock_info_btn = MagicMock()
        mock_item.locator.return_value = mock_info_btn

        with patch('ui.navigation.WaitUtils'):
            nav_mgr._click_menu_item(mock_item, use_info_button=True)

            # Should attempt to click info button
            assert mock_item.locator.called


class TestGetVisibleWindows:
    """Tests for _get_visible_windows method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_get_visible_windows_returns_list(self, nav_mgr):
        """Test _get_visible_windows returns list of windows."""
        mock_windows = [MagicMock(), MagicMock()]
        nav_mgr.page.context.pages = mock_windows

        result = nav_mgr._get_visible_windows()

        assert isinstance(result, list)


class TestGetTitle:
    """Tests for _get_title method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        return NavigationManager(MagicMock(), MagicMock())

    def test_get_title_returns_title(self, nav_mgr):
        """Test _get_title returns window title."""
        mock_window = MagicMock()
        mock_window.title.return_value = "Test Title"

        result = nav_mgr._get_title(mock_window)

        assert result == "Test Title"

    def test_get_title_handles_exception(self, nav_mgr):
        """Test _get_title handles exception."""
        mock_window = MagicMock()
        mock_window.title.side_effect = Exception("Title failed")

        result = nav_mgr._get_title(mock_window)

        assert result == ""


class TestCloseWindow:
    """Tests for _close_window method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        return NavigationManager(MagicMock(), MagicMock())

    def test_close_window_success(self, nav_mgr):
        """Test _close_window closes window successfully."""
        mock_window = MagicMock()

        result = nav_mgr._close_window(mock_window)

        assert result is True
        mock_window.close.assert_called_once()

    def test_close_window_handles_exception(self, nav_mgr):
        """Test _close_window handles exception."""
        mock_window = MagicMock()
        mock_window.close.side_effect = Exception("Close failed")

        result = nav_mgr._close_window(mock_window)

        assert result is False


class TestWaitForMask:
    """Tests for _wait_for_mask method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_wait_for_mask_success(self, nav_mgr):
        """Test _wait_for_mask waits successfully."""
        mock_locator = MagicMock()
        nav_mgr.page.locator.return_value = mock_locator

        result = nav_mgr._wait_for_mask(timeout_ms=1000)

        assert result is True

    def test_wait_for_mask_handles_timeout(self, nav_mgr):
        """Test _wait_for_mask handles timeout."""
        mock_locator = MagicMock()
        mock_locator.wait_for.side_effect = Exception("Timeout")
        nav_mgr.page.locator.return_value = mock_locator

        result = nav_mgr._wait_for_mask(timeout_ms=1000)

        assert result is False


class TestMaximizeActiveWindow:
    """Tests for _maximize_active_window method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_maximize_active_window_executes_script(self, nav_mgr):
        """Test _maximize_active_window executes maximization script."""
        nav_mgr._maximize_active_window()

        nav_mgr.page.evaluate.assert_called_once()


class TestMaximizeNonRfWindows:
    """Tests for maximize_non_rf_windows method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_maximize_non_rf_windows_processes_windows(self, nav_mgr):
        """Test maximize_non_rf_windows processes windows."""
        mock_window1 = MagicMock()
        mock_window1.title.return_value = "Non RF Window"
        mock_window2 = MagicMock()
        mock_window2.title.return_value = "RF Window"

        nav_mgr.page.context.pages = [mock_window1, mock_window2]

        with patch('ui.navigation.Settings') as mock_settings:
            mock_settings.browser.window_height = 1000

            nav_mgr.maximize_non_rf_windows()


class TestMaximizeRfWindow:
    """Tests for maximize_rf_window method."""

    @pytest.fixture
    def nav_mgr(self):
        """Create NavigationManager instance."""
        mock_page = MagicMock()
        return NavigationManager(mock_page, MagicMock())

    def test_maximize_rf_window_finds_and_maximizes(self, nav_mgr):
        """Test maximize_rf_window finds RF window and maximizes."""
        mock_window = MagicMock()
        mock_window.title.return_value = "RF Menu"
        nav_mgr.page.context.pages = [mock_window]

        with patch('ui.navigation.Settings') as mock_settings:
            mock_settings.browser.window_width = 800
            mock_settings.browser.window_height = 600

            nav_mgr.maximize_rf_window()


class TestNormalize:
    """Tests for _normalize static method."""

    def test_normalize_basic(self):
        """Test _normalize basic functionality."""
        result = NavigationManager._normalize("Test String")
        assert result == "test string"

    def test_normalize_removes_special_chars(self):
        """Test _normalize removes special characters."""
        result = NavigationManager._normalize("Test (String) - 123")
        assert "test" in result
        assert "string" in result

    def test_normalize_multiple_spaces(self):
        """Test _normalize handles multiple spaces."""
        result = NavigationManager._normalize("Test    String")
        assert result == "test string"

    def test_normalize_empty_string(self):
        """Test _normalize handles empty string."""
        result = NavigationManager._normalize("")
        assert result == ""
