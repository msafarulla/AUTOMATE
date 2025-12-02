"""
Comprehensive tests for operations/inbound/receive.py to improve coverage.
"""
import pytest
from unittest.mock import MagicMock, Mock, patch, call
from operations.inbound.receive import ReceiveOperation


class TestReceiveOperationInit:
    """Tests for ReceiveOperation initialization."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies."""
        return {
            'page': MagicMock(),
            'page_mgr': MagicMock(),
            'screenshot_mgr': MagicMock(),
            'rf_menu': MagicMock(),
        }

    def test_init_basic(self, mock_dependencies):
        """Test basic initialization."""
        with patch('operations.inbound.receive.RFMenuIntegration') as mock_integration_class, \
             patch('operations.inbound.receive.ReceiveStateMachine') as mock_state_class, \
             patch('operations.inbound.receive.OperationConfig') as mock_config:

            mock_integration = MagicMock()
            mock_integration.get_primitives.return_value = MagicMock()
            mock_integration.get_workflows.return_value = MagicMock()
            mock_integration_class.return_value = mock_integration
            mock_config.RECEIVE_SELECTORS = {"test": "selector"}

            op = ReceiveOperation(**mock_dependencies)

            assert op.page is mock_dependencies['page']
            assert op.screenshot_mgr is mock_dependencies['screenshot_mgr']
            assert op.rf is not None
            assert op.workflows is not None

    def test_init_with_detour_page(self, mock_dependencies):
        """Test initialization with detour page."""
        mock_detour = MagicMock()

        with patch('operations.inbound.receive.RFMenuIntegration'), \
             patch('operations.inbound.receive.ReceiveStateMachine'), \
             patch('operations.inbound.receive.OperationConfig'), \
             patch('operations.inbound.receive.NavigationManager') as mock_nav_class:

            mock_nav = MagicMock()
            mock_nav_class.return_value = mock_nav

            op = ReceiveOperation(**mock_dependencies, detour_page=mock_detour)

            assert op.detour_page is mock_detour
            assert op.detour_nav is mock_nav

    def test_init_without_detour_page(self, mock_dependencies):
        """Test initialization without detour page."""
        with patch('operations.inbound.receive.RFMenuIntegration'), \
             patch('operations.inbound.receive.ReceiveStateMachine'), \
             patch('operations.inbound.receive.OperationConfig'):

            op = ReceiveOperation(**mock_dependencies)

            assert op.detour_page is None
            assert op.detour_nav is None

    def test_init_with_detour_nav_provided(self, mock_dependencies):
        """Test initialization with detour nav provided."""
        mock_detour_page = MagicMock()
        mock_detour_nav = MagicMock()

        with patch('operations.inbound.receive.RFMenuIntegration'), \
             patch('operations.inbound.receive.ReceiveStateMachine'), \
             patch('operations.inbound.receive.OperationConfig'):

            op = ReceiveOperation(
                **mock_dependencies,
                detour_page=mock_detour_page,
                detour_nav=mock_detour_nav
            )

            assert op.detour_nav is mock_detour_nav

    def test_init_with_settings(self, mock_dependencies):
        """Test initialization with settings."""
        mock_settings = MagicMock()

        with patch('operations.inbound.receive.RFMenuIntegration'), \
             patch('operations.inbound.receive.ReceiveStateMachine'), \
             patch('operations.inbound.receive.OperationConfig'):

            op = ReceiveOperation(**mock_dependencies, settings=mock_settings)

            assert op.settings is mock_settings


class TestReceiveOperationExecute:
    """Tests for execute method."""

    @pytest.fixture
    def operation(self):
        """Create ReceiveOperation instance."""
        with patch('operations.inbound.receive.RFMenuIntegration'), \
             patch('operations.inbound.receive.ReceiveStateMachine') as mock_state_class, \
             patch('operations.inbound.receive.OperationConfig'):

            mock_state = MagicMock()
            mock_state.run.return_value = True
            mock_state_class.return_value = mock_state

            op = ReceiveOperation(
                page=MagicMock(),
                page_mgr=MagicMock(),
                screenshot_mgr=MagicMock(),
                rf_menu=MagicMock(),
            )
            return op

    def test_execute_basic(self, operation):
        """Test basic execute call."""
        with patch.object(operation, '_cache_screen_context'):
            result = operation.execute("ASN123", "ITEM001", 10)

            assert result is True
            operation.state_machine.run.assert_called_once()

    def test_execute_passes_parameters(self, operation):
        """Test execute passes all parameters to state machine."""
        with patch.object(operation, '_cache_screen_context'):
            operation.execute(
                "ASN123",
                "ITEM001",
                10,
                flow_hint="test_flow",
                auto_handle=True
            )

            call_args = operation.state_machine.run.call_args
            assert call_args[1]['asn'] == "ASN123"
            assert call_args[1]['item'] == "ITEM001"
            assert call_args[1]['quantity'] == 10
            assert call_args[1]['flow_hint'] == "test_flow"
            assert call_args[1]['auto_handle'] is True

    def test_execute_without_open_ui_cfg(self, operation):
        """Test execute without open_ui_cfg doesn't create hooks."""
        with patch.object(operation, '_cache_screen_context'):
            operation.execute("ASN123", "ITEM001", 10, open_ui_cfg=None)

            call_args = operation.state_machine.run.call_args
            assert call_args[1]['post_qty_hook'] is None
            assert call_args[1]['post_location_hook'] is None

    def test_execute_with_open_ui_cfg_creates_hooks(self, operation):
        """Test execute with open_ui_cfg creates hooks."""
        with patch.object(operation, '_cache_screen_context'):
            cfg = {"test": "config"}
            operation.execute("ASN123", "ITEM001", 10, open_ui_cfg=cfg)

            call_args = operation.state_machine.run.call_args
            assert call_args[1]['post_qty_hook'] is not None
            assert call_args[1]['post_location_hook'] is not None

    def test_execute_caches_context(self, operation):
        """Test execute caches screen context."""
        with patch.object(operation, '_cache_screen_context') as mock_cache:
            operation.execute("ASN123", "ITEM001", 10)

            mock_cache.assert_called_once()

    def test_execute_returns_state_machine_result(self, operation):
        """Test execute returns state machine result."""
        operation.state_machine.run.return_value = False

        with patch.object(operation, '_cache_screen_context'):
            result = operation.execute("ASN123", "ITEM001", 10)

            assert result is False


class TestFillIlpnQuickFilter:
    """Tests for _fill_ilpn_quick_filter method."""

    @pytest.fixture
    def operation(self):
        """Create ReceiveOperation instance."""
        with patch('operations.inbound.receive.RFMenuIntegration'), \
             patch('operations.inbound.receive.ReceiveStateMachine'), \
             patch('operations.inbound.receive.OperationConfig'):

            return ReceiveOperation(
                page=MagicMock(),
                page_mgr=MagicMock(),
                screenshot_mgr=MagicMock(),
                rf_menu=MagicMock(),
            )

    def test_fill_ilpn_success(self, operation):
        """Test _fill_ilpn_quick_filter success."""
        with patch('operations.inbound.receive.fill_ilpn_filter') as mock_fill:
            mock_fill.return_value = True

            result = operation._fill_ilpn_quick_filter("ILPN123")

            assert result is True
            mock_fill.assert_called_once()

    def test_fill_ilpn_uses_default_page(self, operation):
        """Test _fill_ilpn_quick_filter uses default page."""
        with patch('operations.inbound.receive.fill_ilpn_filter') as mock_fill:
            mock_fill.return_value = True

            operation._fill_ilpn_quick_filter("ILPN123")

            call_args = mock_fill.call_args
            assert call_args[0][0] is operation.page

    def test_fill_ilpn_uses_custom_page(self, operation):
        """Test _fill_ilpn_quick_filter uses custom page."""
        mock_custom_page = MagicMock()

        with patch('operations.inbound.receive.fill_ilpn_filter') as mock_fill:
            mock_fill.return_value = True

            operation._fill_ilpn_quick_filter("ILPN123", page=mock_custom_page)

            call_args = mock_fill.call_args
            assert call_args[0][0] is mock_custom_page

    def test_fill_ilpn_passes_kwargs(self, operation):
        """Test _fill_ilpn_quick_filter passes kwargs."""
        with patch('operations.inbound.receive.fill_ilpn_filter') as mock_fill:
            mock_fill.return_value = True

            operation._fill_ilpn_quick_filter("ILPN123", extra_arg="value")

            call_args = mock_fill.call_args
            assert call_args[1]['extra_arg'] == "value"

    def test_fill_ilpn_handles_exception(self, operation):
        """Test _fill_ilpn_quick_filter handles exception."""
        with patch('operations.inbound.receive.fill_ilpn_filter') as mock_fill:
            mock_fill.side_effect = Exception("Fill failed")

            result = operation._fill_ilpn_quick_filter("ILPN123")

            assert result is False


class TestCacheScreenContext:
    """Tests for _cache_screen_context method."""

    @pytest.fixture
    def operation(self):
        """Create ReceiveOperation instance."""
        with patch('operations.inbound.receive.RFMenuIntegration'), \
             patch('operations.inbound.receive.ReceiveStateMachine'), \
             patch('operations.inbound.receive.OperationConfig'):

            return ReceiveOperation(
                page=MagicMock(),
                page_mgr=MagicMock(),
                screenshot_mgr=MagicMock(),
                rf_menu=MagicMock(),
            )

    def test_cache_context_with_valid_context(self, operation):
        """Test _cache_screen_context with valid state machine context."""
        mock_context = MagicMock()
        mock_context.asn = "ASN123"
        mock_context.item = "ITEM001"
        mock_context.quantity = 10
        mock_context.shipped_qty = 100
        mock_context.received_qty = 50
        mock_context.ilpn = "ILPN123"
        mock_context.suggested_location = "LOC-A-1"
        mock_context.flow_hint = "test_flow"

        operation.state_machine.context = mock_context

        operation._cache_screen_context()

        assert operation._screen_context is not None
        assert operation._screen_context['asn'] == "ASN123"
        assert operation._screen_context['item'] == "ITEM001"
        assert operation._screen_context['quantity'] == 10

    def test_cache_context_without_context(self, operation):
        """Test _cache_screen_context without state machine context."""
        operation.state_machine.context = None

        operation._cache_screen_context()

        assert operation._screen_context is None

    def test_cache_context_no_context_attribute(self, operation):
        """Test _cache_screen_context when state machine has no context attribute."""
        delattr(operation.state_machine, 'context')

        operation._cache_screen_context()

        assert operation._screen_context is None


class TestOnQtyEntered:
    """Tests for _on_qty_entered method."""

    @pytest.fixture
    def operation(self):
        """Create ReceiveOperation instance."""
        with patch('operations.inbound.receive.RFMenuIntegration'), \
             patch('operations.inbound.receive.ReceiveStateMachine'), \
             patch('operations.inbound.receive.OperationConfig'):

            return ReceiveOperation(
                page=MagicMock(),
                page_mgr=MagicMock(),
                screenshot_mgr=MagicMock(),
                rf_menu=MagicMock(),
            )

    def test_on_qty_entered_with_cfg(self, operation):
        """Test _on_qty_entered with config."""
        cfg = {"test": "config"}

        with patch('operations.inbound.receive.WaitUtils'), \
             patch.object(operation, '_cache_screen_context'), \
             patch.object(operation, '_handle_open_ui'):

            operation._on_qty_entered(cfg)

            operation._cache_screen_context.assert_called_once()
            operation._handle_open_ui.assert_called_once_with(cfg)

    def test_on_qty_entered_without_cfg(self, operation):
        """Test _on_qty_entered without config returns early."""
        with patch.object(operation, '_cache_screen_context') as mock_cache, \
             patch.object(operation, '_handle_open_ui') as mock_handle:

            operation._on_qty_entered(None)

            mock_cache.assert_not_called()
            mock_handle.assert_not_called()


class TestOnSuggestedLocation:
    """Tests for _on_suggested_location method."""

    @pytest.fixture
    def operation(self):
        """Create ReceiveOperation instance."""
        with patch('operations.inbound.receive.RFMenuIntegration'), \
             patch('operations.inbound.receive.ReceiveStateMachine'), \
             patch('operations.inbound.receive.OperationConfig'):

            return ReceiveOperation(
                page=MagicMock(),
                page_mgr=MagicMock(),
                screenshot_mgr=MagicMock(),
                rf_menu=MagicMock(),
            )

    def test_on_suggested_location_with_cfg(self, operation):
        """Test _on_suggested_location with config."""
        cfg = {"test": "config"}

        with patch.object(operation, '_cache_screen_context'), \
             patch.object(operation, '_handle_open_ui'):

            operation._on_suggested_location(cfg)

            operation._cache_screen_context.assert_called_once()
            operation._handle_open_ui.assert_called_once_with(cfg)

    def test_on_suggested_location_without_cfg(self, operation):
        """Test _on_suggested_location without config returns early."""
        with patch.object(operation, '_cache_screen_context') as mock_cache, \
             patch.object(operation, '_handle_open_ui') as mock_handle:

            operation._on_suggested_location(None)

            mock_cache.assert_not_called()
            mock_handle.assert_not_called()


class TestHandleOpenUI:
    """Tests for _handle_open_ui method."""

    @pytest.fixture
    def operation(self):
        """Create ReceiveOperation instance."""
        with patch('operations.inbound.receive.RFMenuIntegration'), \
             patch('operations.inbound.receive.ReceiveStateMachine'), \
             patch('operations.inbound.receive.OperationConfig'):

            op = ReceiveOperation(
                page=MagicMock(),
                page_mgr=MagicMock(),
                screenshot_mgr=MagicMock(),
                rf_menu=MagicMock(),
            )
            op._screen_context = {"asn": "ASN123"}
            return op

    def test_handle_open_ui_calls_detour_runner(self, operation):
        """Test _handle_open_ui calls run_open_ui_detours."""
        cfg = {"test": "config"}

        with patch('operations.inbound.receive.run_open_ui_detours') as mock_detour, \
             patch('operations.inbound.receive.NavigationManager'), \
             patch.object(operation, '_ensure_detour_nav'):

            operation._handle_open_ui(cfg)

            mock_detour.assert_called_once()

    def test_handle_open_ui_ensures_detour_nav(self, operation):
        """Test _handle_open_ui ensures detour nav exists."""
        cfg = {"test": "config"}

        with patch('operations.inbound.receive.run_open_ui_detours'), \
             patch('operations.inbound.receive.NavigationManager'), \
             patch.object(operation, '_ensure_detour_nav') as mock_ensure:

            operation._handle_open_ui(cfg)

            mock_ensure.assert_called_once()

    def test_handle_open_ui_passes_screen_context(self, operation):
        """Test _handle_open_ui passes screen context."""
        cfg = {"test": "config"}

        with patch('operations.inbound.receive.run_open_ui_detours') as mock_detour, \
             patch('operations.inbound.receive.NavigationManager'), \
             patch.object(operation, '_ensure_detour_nav'):

            operation._handle_open_ui(cfg)

            call_args = mock_detour.call_args
            assert call_args[1]['screen_context'] == {"asn": "ASN123"}


class TestEnsureDetourNav:
    """Tests for _ensure_detour_nav method."""

    @pytest.fixture
    def operation(self):
        """Create ReceiveOperation instance."""
        with patch('operations.inbound.receive.RFMenuIntegration'), \
             patch('operations.inbound.receive.ReceiveStateMachine'), \
             patch('operations.inbound.receive.OperationConfig'):

            mock_page = MagicMock()
            mock_page.context.new_page.return_value = MagicMock()

            return ReceiveOperation(
                page=mock_page,
                page_mgr=MagicMock(),
                screenshot_mgr=MagicMock(),
                rf_menu=MagicMock(),
            )

    def test_ensure_detour_nav_returns_early_when_exists(self, operation):
        """Test _ensure_detour_nav returns early when detour nav exists."""
        operation.detour_page = MagicMock()
        operation.detour_nav = MagicMock()

        operation._ensure_detour_nav()

        # Should not create new page
        operation.page.context.new_page.assert_not_called()

    def test_ensure_detour_nav_creates_new_page(self, operation):
        """Test _ensure_detour_nav creates new page when needed."""
        operation.detour_page = None
        operation.detour_nav = None

        with patch('operations.inbound.receive.NavigationManager') as mock_nav_class:
            operation._ensure_detour_nav()

            operation.page.context.new_page.assert_called_once()
            assert operation.detour_page is not None
            assert operation.detour_nav is not None

    def test_ensure_detour_nav_handles_exception(self, operation):
        """Test _ensure_detour_nav handles new_page exception."""
        operation.detour_page = None
        operation.detour_nav = None
        operation.page.context.new_page.side_effect = Exception("New page failed")

        operation._ensure_detour_nav()

        assert operation.detour_page is None
        assert operation.detour_nav is None
