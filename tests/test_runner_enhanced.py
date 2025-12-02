"""
Comprehensive tests for operations/runner.py to improve coverage.
"""
import pytest
from unittest.mock import MagicMock, Mock, patch, call
from operations.runner import OperationRunner, OperationServices, create_operation_services
from core.connection_guard import ConnectionResetGuard


class TestOperationRunner:
    """Tests for OperationRunner class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.app.change_warehouse = "WH01"
        settings.app.post_message_text = "Test message"
        return settings

    @pytest.fixture
    def mock_page(self):
        """Create mock page."""
        page = MagicMock()
        page.context.new_page.return_value = MagicMock()
        return page

    @pytest.fixture
    def mock_conn_guard(self):
        """Create mock connection guard that returns guarded functions."""
        guard = MagicMock(spec=ConnectionResetGuard)
        # Make guarded() return the original function for testing
        guard.guarded = lambda func: func
        return guard

    @pytest.fixture
    def runner(self, mock_settings, mock_page, mock_conn_guard):
        """Create OperationRunner instance."""
        return OperationRunner(
            settings=mock_settings,
            page=mock_page,
            page_mgr=MagicMock(),
            screenshot_mgr=MagicMock(),
            auth_mgr=MagicMock(),
            nav_mgr=MagicMock(),
            detour_page=None,
            rf_menu=MagicMock(),
            conn_guard=mock_conn_guard,
        )

    def test_init_sets_attributes(self, runner, mock_settings, mock_page):
        """Test initialization sets all attributes."""
        assert runner.settings is mock_settings
        assert runner.page is mock_page
        assert runner.page_mgr is not None
        assert runner.screenshot_mgr is not None
        assert runner.auth_mgr is not None
        assert runner.nav_mgr is not None

    def test_init_creates_detour_nav_when_detour_page_provided(self):
        """Test initialization creates detour nav when detour page provided."""
        mock_detour_page = MagicMock()
        mock_conn_guard = MagicMock()
        mock_conn_guard.guarded = lambda func: func

        with patch('operations.runner.NavigationManager') as mock_nav_class:
            mock_nav_instance = MagicMock()
            mock_nav_class.return_value = mock_nav_instance

            runner = OperationRunner(
                settings=MagicMock(),
                page=MagicMock(),
                page_mgr=MagicMock(),
                screenshot_mgr=MagicMock(),
                auth_mgr=MagicMock(),
                nav_mgr=MagicMock(),
                detour_page=mock_detour_page,
                rf_menu=MagicMock(),
                conn_guard=mock_conn_guard,
            )

            assert runner.detour_nav is mock_nav_instance
            mock_nav_class.assert_called_once_with(mock_detour_page, runner.screenshot_mgr)

    def test_init_no_detour_nav_when_no_detour_page(self, runner):
        """Test initialization doesn't create detour nav when no detour page."""
        assert runner.detour_nav is None

    def test_run_login_calls_auth_mgr(self, runner):
        """Test run_login delegates to auth manager."""
        runner._run_login()
        runner.auth_mgr.login.assert_called_once()

    def test_run_change_warehouse_calls_nav_mgr(self, runner, mock_settings):
        """Test run_change_warehouse delegates to nav manager."""
        runner._run_change_warehouse()
        runner.nav_mgr.change_warehouse.assert_called_once_with("WH01")

    def test_receive_impl_opens_rf_menu(self, runner):
        """Test _receive_impl opens RF menu."""
        with patch('operations.runner.ReceiveOperation') as mock_receive_class:
            mock_receive = MagicMock()
            mock_receive.execute.return_value = True
            mock_receive_class.return_value = mock_receive

            runner._receive_impl("ASN123", "ITEM001", 5)

            runner.nav_mgr.open_menu_item.assert_called_once_with(
                "RF MENU", "RF Menu (Distribution)"
            )

    def test_receive_impl_creates_receive_operation(self, runner):
        """Test _receive_impl creates ReceiveOperation."""
        with patch('operations.runner.ReceiveOperation') as mock_receive_class:
            mock_receive = MagicMock()
            mock_receive.execute.return_value = True
            mock_receive_class.return_value = mock_receive

            result = runner._receive_impl("ASN123", "ITEM001", 5)

            mock_receive_class.assert_called_once()
            assert result is True

    def test_receive_impl_passes_parameters(self, runner):
        """Test _receive_impl passes all parameters correctly."""
        with patch('operations.runner.ReceiveOperation') as mock_receive_class:
            mock_receive = MagicMock()
            mock_receive.execute.return_value = True
            mock_receive_class.return_value = mock_receive

            runner._receive_impl(
                "ASN123",
                "ITEM001",
                10,
                flow_hint="test_flow",
                auto_handle=True,
                open_ui_cfg={"key": "value"}
            )

            mock_receive.execute.assert_called_once_with(
                "ASN123",
                "ITEM001",
                10,
                flow_hint="test_flow",
                auto_handle=True,
                open_ui_cfg={"key": "value"}
            )

    def test_loading_impl_opens_rf_menu(self, runner):
        """Test _loading_impl opens RF menu."""
        with patch('operations.runner.LoadingOperation') as mock_load_class:
            mock_load = MagicMock()
            mock_load.execute.return_value = True
            mock_load_class.return_value = mock_load

            runner._loading_impl("SHIP123", "DOCK01", "BOL456")

            runner.nav_mgr.open_menu_item.assert_called_once_with(
                "RF MENU", "RF Menu (Distribution)"
            )

    def test_loading_impl_creates_loading_operation(self, runner):
        """Test _loading_impl creates LoadingOperation."""
        with patch('operations.runner.LoadingOperation') as mock_load_class:
            mock_load = MagicMock()
            mock_load.execute.return_value = True
            mock_load_class.return_value = mock_load

            result = runner._loading_impl("SHIP123", "DOCK01", "BOL456")

            mock_load_class.assert_called_once()
            assert result is True

    def test_post_impl_opens_post_menu(self, runner):
        """Test _post_impl opens Post Message menu."""
        with patch('operations.runner.PostMessageManager') as mock_post_class:
            mock_post = MagicMock()
            mock_post.send_message.return_value = (True, {"summary": "Success", "payload": {}})
            mock_post_class.return_value = mock_post

            runner._post_impl("Test payload")

            runner.nav_mgr.open_menu_item.assert_called_once_with(
                "POST", "Post Message (Integration)"
            )

    def test_post_impl_maximizes_window(self, runner):
        """Test _post_impl tries to maximize non-RF windows."""
        with patch('operations.runner.PostMessageManager') as mock_post_class:
            mock_post = MagicMock()
            mock_post.send_message.return_value = (True, {"summary": "Success", "payload": {}})
            mock_post_class.return_value = mock_post

            runner._post_impl("Test payload")

            runner.nav_mgr.maximize_non_rf_windows.assert_called_once()

    def test_post_impl_handles_maximize_exception(self, runner):
        """Test _post_impl continues if maximize fails."""
        runner.nav_mgr.maximize_non_rf_windows.side_effect = Exception("Maximize failed")

        with patch('operations.runner.PostMessageManager') as mock_post_class:
            mock_post = MagicMock()
            mock_post.send_message.return_value = (True, {"summary": "Success", "payload": {}})
            mock_post_class.return_value = mock_post

            result = runner._post_impl("Test payload")

            assert result is True  # Should continue despite exception

    def test_post_impl_uses_provided_payload(self, runner):
        """Test _post_impl uses provided payload."""
        with patch('operations.runner.PostMessageManager') as mock_post_class:
            mock_post = MagicMock()
            mock_post.send_message.return_value = (True, {"summary": "Success", "payload": {}})
            mock_post_class.return_value = mock_post

            runner._post_impl("Custom payload")

            mock_post.send_message.assert_called_once_with("Custom payload")

    def test_post_impl_uses_default_payload_when_none_provided(self, runner, mock_settings):
        """Test _post_impl uses settings payload when none provided."""
        with patch('operations.runner.PostMessageManager') as mock_post_class:
            mock_post = MagicMock()
            mock_post.send_message.return_value = (True, {"summary": "Success", "payload": {}})
            mock_post_class.return_value = mock_post

            runner._post_impl(None)

            mock_post.send_message.assert_called_once_with("Test message")

    def test_post_impl_returns_false_when_no_payload(self, runner, mock_settings):
        """Test _post_impl returns False when no payload available."""
        mock_settings.app.post_message_text = None

        result = runner._post_impl(None)

        assert result is False

    def test_post_impl_returns_false_when_send_fails(self, runner):
        """Test _post_impl returns False when send fails."""
        with patch('operations.runner.PostMessageManager') as mock_post_class:
            mock_post = MagicMock()
            mock_post.send_message.return_value = (False, {"summary": "Error", "payload": {}})
            mock_post_class.return_value = mock_post

            result = runner._post_impl("Test payload")

            assert result is False

    def test_post_impl_returns_true_when_send_succeeds(self, runner):
        """Test _post_impl returns True when send succeeds."""
        with patch('operations.runner.PostMessageManager') as mock_post_class:
            mock_post = MagicMock()
            mock_post.send_message.return_value = (True, {"summary": "Success", "payload": {}})
            mock_post_class.return_value = mock_post

            result = runner._post_impl("Test payload")

            assert result is True

    def test_post_impl_logs_response_payload(self, runner):
        """Test _post_impl logs response payload when present."""
        with patch('operations.runner.PostMessageManager') as mock_post_class, \
             patch('operations.runner.app_log') as mock_log:
            mock_post = MagicMock()
            mock_post.send_message.return_value = (True, {
                "summary": "Success",
                "payload": {"key": "value"}
            })
            mock_post_class.return_value = mock_post

            runner._post_impl("Test payload")

            # Check that payload was logged
            log_calls = [str(call) for call in mock_log.call_args_list]
            assert any("payload" in str(call) for call in log_calls)

    def test_run_open_ui_calls_nav_mgr(self, runner):
        """Test _run_open_ui delegates to nav manager."""
        runner.nav_mgr.open_menu_item.return_value = True

        result = runner._run_open_ui("SEARCH", "Match Text")

        runner.nav_mgr.open_menu_item.assert_called_once_with("SEARCH", "Match Text")
        assert result is True

    def test_run_open_ui_returns_false_on_failure(self, runner):
        """Test _run_open_ui returns False when navigation fails."""
        runner.nav_mgr.open_menu_item.return_value = False

        result = runner._run_open_ui("SEARCH", "Match Text")

        assert result is False

    def test_get_detour_resources_returns_existing(self, mock_conn_guard):
        """Test _get_detour_resources returns existing detour page/nav."""
        mock_detour_page = MagicMock()
        mock_detour_nav = MagicMock()
        mock_conn_guard.guarded = lambda func: func

        runner = OperationRunner(
            settings=MagicMock(),
            page=MagicMock(),
            page_mgr=MagicMock(),
            screenshot_mgr=MagicMock(),
            auth_mgr=MagicMock(),
            nav_mgr=MagicMock(),
            detour_page=mock_detour_page,
            rf_menu=MagicMock(),
            conn_guard=mock_conn_guard,
        )

        page, nav = runner._get_detour_resources()

        assert page is not None
        assert nav is not None

    def test_get_detour_resources_creates_new_page(self, runner, mock_page):
        """Test _get_detour_resources creates new page when needed."""
        assert runner.detour_page is None

        with patch('operations.runner.NavigationManager') as mock_nav_class:
            page, nav = runner._get_detour_resources()

            mock_page.context.new_page.assert_called_once()
            assert runner.detour_page is not None

    def test_get_detour_resources_brings_main_page_to_front(self, runner, mock_page):
        """Test _get_detour_resources brings main page to front after creating new page."""
        with patch('operations.runner.NavigationManager'):
            runner._get_detour_resources()

            mock_page.bring_to_front.assert_called_once()

    def test_get_detour_resources_handles_bring_to_front_exception(self, runner, mock_page):
        """Test _get_detour_resources handles bring_to_front exception gracefully."""
        mock_page.bring_to_front.side_effect = Exception("Bring to front failed")

        with patch('operations.runner.NavigationManager'):
            page, nav = runner._get_detour_resources()

            # Should still succeed despite exception
            assert page is not None

    def test_get_detour_resources_handles_new_page_exception(self, runner, mock_page):
        """Test _get_detour_resources handles new_page exception."""
        mock_page.context.new_page.side_effect = Exception("New page failed")

        page, nav = runner._get_detour_resources()

        assert page is None
        assert nav is None
        assert runner.detour_page is None
        assert runner.detour_nav is None


class TestOperationServices:
    """Tests for OperationServices dataclass."""

    def test_operation_services_creation(self):
        """Test OperationServices can be created with all fields."""
        services = OperationServices(
            screenshot_mgr=MagicMock(),
            nav_mgr=MagicMock(),
            orchestrator=MagicMock(),
            step_execution=MagicMock(),
            executor=MagicMock(),
        )

        assert services.screenshot_mgr is not None
        assert services.nav_mgr is not None
        assert services.orchestrator is not None
        assert services.step_execution is not None
        assert services.executor is not None


class TestCreateOperationServices:
    """Tests for create_operation_services context manager."""

    def test_create_operation_services_yields_services(self):
        """Test create_operation_services yields OperationServices."""
        mock_settings = MagicMock()
        mock_settings.browser.screenshot_dir = "/tmp"
        mock_settings.browser.screenshot_format = "png"
        mock_settings.browser.screenshot_quality = 80
        mock_settings.app.rf_verbose_logging = False
        mock_settings.app.auto_click_info_icon = False
        mock_settings.app.show_tran_id = False

        with patch('operations.runner.BrowserManager') as mock_browser_class, \
             patch('operations.runner.PageManager'), \
             patch('operations.runner.ScreenshotManager'), \
             patch('operations.runner.AuthManager'), \
             patch('operations.runner.NavigationManager'), \
             patch('operations.runner.RFMenuManager'), \
             patch('operations.runner.ConnectionResetGuard'), \
             patch('operations.runner.AutomationOrchestrator'), \
             patch('operations.runner.OperationRunner'), \
             patch('operations.runner.StepExecution'), \
             patch('operations.runner.WorkflowStageExecutor'):

            mock_browser = MagicMock()
            mock_browser.__enter__ = MagicMock(return_value=mock_browser)
            mock_browser.__exit__ = MagicMock(return_value=False)
            mock_browser.new_page = MagicMock()
            mock_browser_class.return_value = mock_browser

            with create_operation_services(mock_settings) as services:
                assert isinstance(services, OperationServices)
                assert services.screenshot_mgr is not None
                assert services.nav_mgr is not None
                assert services.orchestrator is not None
                assert services.step_execution is not None
                assert services.executor is not None

    def test_create_operation_services_creates_all_components(self):
        """Test create_operation_services creates all required components."""
        mock_settings = MagicMock()
        mock_settings.browser.screenshot_dir = "/tmp"
        mock_settings.browser.screenshot_format = "png"
        mock_settings.browser.screenshot_quality = 80
        mock_settings.app.rf_verbose_logging = False
        mock_settings.app.auto_click_info_icon = False
        mock_settings.app.show_tran_id = False

        with patch('operations.runner.BrowserManager') as mock_browser_class, \
             patch('operations.runner.PageManager') as mock_page_mgr_class, \
             patch('operations.runner.ScreenshotManager') as mock_screenshot_class, \
             patch('operations.runner.AuthManager') as mock_auth_class, \
             patch('operations.runner.NavigationManager') as mock_nav_class, \
             patch('operations.runner.RFMenuManager') as mock_rf_class, \
             patch('operations.runner.ConnectionResetGuard') as mock_guard_class, \
             patch('operations.runner.AutomationOrchestrator') as mock_orch_class, \
             patch('operations.runner.OperationRunner') as mock_runner_class, \
             patch('operations.runner.StepExecution') as mock_step_class, \
             patch('operations.runner.WorkflowStageExecutor') as mock_exec_class:

            mock_browser = MagicMock()
            mock_browser.__enter__ = MagicMock(return_value=mock_browser)
            mock_browser.__exit__ = MagicMock(return_value=False)
            mock_browser.new_page = MagicMock(return_value=MagicMock())
            mock_browser_class.return_value = mock_browser

            with create_operation_services(mock_settings) as services:
                # Verify all components were created
                mock_browser_class.assert_called_once_with(mock_settings)
                mock_page_mgr_class.assert_called_once()
                mock_screenshot_class.assert_called_once()
                mock_auth_class.assert_called_once()
                mock_nav_class.assert_called()
                mock_rf_class.assert_called_once()
                mock_guard_class.assert_called_once()
                mock_orch_class.assert_called_once()
                mock_runner_class.assert_called_once()
                mock_step_class.assert_called_once()
                mock_exec_class.assert_called_once()
