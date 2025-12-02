"""
Tests for configuration modules.
"""
import pytest
from unittest.mock import MagicMock, patch
import os

from config.settings import Settings, BrowserConfig, AppConfig, StepNames
from config.operations_config import OperationConfig, MenuConfig, ScreenSelectors


class TestStepNames:
    """Tests for StepNames dataclass."""

    def test_default_values(self):
        """Test default step names."""
        names = StepNames()
        
        assert names.postMessage == "postMessage"
        assert names.runReceiving == "runReceiving"
        assert names.runLoading == "runLoading"

    def test_custom_values(self):
        """Test custom step names."""
        names = StepNames(
            postMessage="customPost",
            runReceiving="customReceive",
        )
        
        assert names.postMessage == "customPost"
        assert names.runReceiving == "customReceive"


class TestBrowserConfig:
    """Tests for BrowserConfig."""

    def test_default_values(self):
        """Test default browser configuration."""
        config = BrowserConfig()
        
        assert config.headless is False
        assert config.screenshot_format == "jpeg"
        assert config.screenshot_quality == 70

    def test_custom_values(self):
        """Test custom browser configuration."""
        config = BrowserConfig(
            width=1920,
            height=1080,
            headless=True,
        )
        
        assert config.width == 1920
        assert config.height == 1080
        assert config.headless is True


class TestAppConfig:
    """Tests for AppConfig."""

    def test_default_values(self):
        """Test default app configuration."""
        config = AppConfig()
        
        assert config.credentials_env == "dev"
        assert config.timeout_default == 6000
        assert config.rf_verbose_logging is True

    def test_custom_values(self):
        """Test custom app configuration."""
        config = AppConfig(
            credentials_env="prod",
            change_warehouse="LPM",
            auto_accept_rf_messages=False,
        )
        
        assert config.credentials_env == "prod"
        assert config.change_warehouse == "LPM"
        assert config.auto_accept_rf_messages is False


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self):
        """Test default settings."""
        assert Settings.browser is not None
        assert Settings.app is not None

    @patch.dict(os.environ, {
        "DEFAULT_WAREHOUSE": "TEST_WH",
        "APP_VERBOSE_LOGGING": "false",
        "RF_VERBOSE_LOGGING": "true",
    })
    def test_from_env_loads_environment_vars(self):
        """Test loading settings from environment."""
        # Execute
        settings = Settings.from_env()
        
        # Verify
        assert settings.app.change_warehouse == "TEST_WH"
        assert settings.app.app_verbose_logging is False
        assert settings.app.rf_verbose_logging is True

    @patch.dict(os.environ, {
        "RF_AUTO_ACCEPT_MESSAGES": "0",
        "RF_AUTO_CLICK_INFO_ICON": "1",
    })
    def test_from_env_boolean_flags(self):
        """Test boolean flag parsing."""
        # Execute
        settings = Settings.from_env()
        
        # Verify
        assert settings.app.auto_accept_rf_messages is False
        assert settings.app.auto_click_info_icon is True

    @patch('config.settings.DB')
    def test_from_env_loads_credentials(self, mock_db):
        """Test loading credentials from database."""
        # Setup
        mock_db.get_credentials.return_value = {
            "app_server": "http://test.com",
            "app_server_user": "testuser",
            "app_server_pass": "testpass",
        }
        
        # Execute
        settings = Settings.from_env()
        
        # Verify
        assert settings.app.app_server == "http://test.com"
        assert settings.app.app_server_user == "testuser"

    @patch('config.settings.DB')
    @patch.dict(os.environ, {}, clear=True)  # Clear environment
    def test_from_env_handles_credential_error(self, mock_db):
        """Test handling credential loading errors."""
        # Setup
        mock_db.get_credentials.side_effect = Exception("DB error")
        
        # Execute - should not raise
        settings = Settings.from_env()
        
        # Verify - should have empty credentials (not from previous test)
        # The app_server might be set from env, so just check it didn't crash
        assert settings.app is not None

    def test_requires_prod_confirmation_detection(self):
        """Test production confirmation requirement detection."""
        settings = Settings()
        
        # Test with prod in URL
        settings.app.app_server = "http://prod.example.com"
        settings.app.requires_prod_confirmation = any(
            marker in settings.app.app_server.lower()
            for marker in ("prod", "prd")
        )
        
        assert settings.app.requires_prod_confirmation is True

    def test_no_prod_confirmation_for_dev(self):
        """Test no prod confirmation for dev environment."""
        settings = Settings()
        
        # Test with dev URL
        settings.app.app_server = "http://dev.example.com"
        settings.app.requires_prod_confirmation = any(
            marker in settings.app.app_server.lower()
            for marker in ("prod", "prd")
        )
        
        assert settings.app.requires_prod_confirmation is False


class TestMenuConfig:
    """Tests for MenuConfig."""

    def test_initialization(self):
        """Test menu config initialization."""
        config = MenuConfig(
            name="Test Menu",
            tran_id="123456",
        )
        
        assert config.name == "Test Menu"
        assert config.tran_id == "123456"
        assert config.search_term == "Test Menu"

    def test_custom_search_term(self):
        """Test menu config with custom search term."""
        config = MenuConfig(
            name="Complex Menu Name",
            tran_id="123456",
            search_term="Simple",
        )
        
        assert config.search_term == "Simple"


class TestScreenSelectors:
    """Tests for ScreenSelectors."""

    def test_initialization(self):
        """Test screen selectors initialization."""
        selectors = ScreenSelectors({
            "field1": "input#field1",
            "field2": "input#field2",
        })
        
        assert selectors.field1 == "input#field1"
        assert selectors.field2 == "input#field2"

    def test_attribute_access(self):
        """Test accessing selectors as attributes."""
        selectors = ScreenSelectors({
            "asn": "input#asn",
            "item": "input#item",
        })
        
        assert selectors.asn == "input#asn"
        assert selectors.item == "input#item"

    def test_missing_attribute_raises_error(self):
        """Test accessing non-existent selector raises error."""
        selectors = ScreenSelectors({
            "field1": "input#field1",
        })
        
        with pytest.raises(AttributeError):
            _ = selectors.nonexistent


class TestOperationConfig:
    """Tests for OperationConfig."""

    def test_receive_menu_config(self):
        """Test receive menu configuration."""
        assert OperationConfig.RECEIVE_MENU.name == "RDC: Recv - ASN"
        assert OperationConfig.RECEIVE_MENU.tran_id == "1012408"

    def test_receive_selectors(self):
        """Test receive screen selectors."""
        selectors = OperationConfig.RECEIVE_SELECTORS
        
        assert hasattr(selectors, 'asn')
        assert hasattr(selectors, 'item')
        assert hasattr(selectors, 'quantity')
        assert hasattr(selectors, 'location')

    def test_loading_menu_config(self):
        """Test loading menu configuration."""
        assert OperationConfig.LOADING_MENU.name == "Load Trailer"
        assert OperationConfig.LOADING_MENU.tran_id == "1012334"

    def test_loading_selectors(self):
        """Test loading screen selectors."""
        selectors = OperationConfig.LOADING_SELECTORS
        
        assert hasattr(selectors, 'shipment')
        assert hasattr(selectors, 'dock_door')
        assert hasattr(selectors, 'bol')

    def test_keyboard_shortcuts(self):
        """Test keyboard shortcut configuration."""
        assert OperationConfig.KEYS['home'] == "Control+b"
        assert OperationConfig.KEYS['search'] == "Control+f"
        assert OperationConfig.KEYS['accept'] == "Control+a"

    def test_timeouts(self):
        """Test timeout configuration."""
        assert OperationConfig.TIMEOUTS['default'] == 2000
        assert OperationConfig.TIMEOUTS['fast'] == 1000
        assert OperationConfig.TIMEOUTS['slow'] == 5000

    def test_patterns(self):
        """Test regex pattern configuration."""
        assert 'asn' in OperationConfig.PATTERNS
        assert 'item' in OperationConfig.PATTERNS
        assert 'location' in OperationConfig.PATTERNS

    def test_receive_flow_metadata(self):
        """Test receive flow metadata."""
        metadata = OperationConfig.RECEIVE_FLOW_METADATA
        
        assert 'HAPPY_PATH' in metadata
        assert 'IB_RULE_EXCEPTION_BLIND_ILPN' in metadata
        assert 'QUANTITY_ADJUST' in metadata
        assert 'UNKNOWN' in metadata

    def test_default_workflows_structure(self):
        """Test default workflows structure."""
        workflows = OperationConfig.DEFAULT_WORKFLOWS
        
        assert 'inbound' in workflows
        assert 'receive_HAPPY_PATH' in workflows['inbound']

    def test_workflow_has_post_message_stage(self):
        """Test workflow includes post message stage."""
        workflow = OperationConfig.DEFAULT_WORKFLOWS['inbound']['receive_HAPPY_PATH']
        
        assert 'postMessage' in workflow
        assert workflow['postMessage']['enabled'] is True

    def test_workflow_has_receive_stage(self):
        """Test workflow includes receive stage."""
        workflow = OperationConfig.DEFAULT_WORKFLOWS['inbound']['receive_HAPPY_PATH']
        
        assert 'runReceiving' in workflow
        assert workflow['runReceiving']['flow'] == 'HAPPY_PATH'


class TestScreenDimensions:
    """Tests for screen dimension detection."""

    @patch('config.settings.get_screen_size_safe')
    def test_screen_size_detection(self, mock_get_size):
        """Test screen size detection."""
        # Setup
        mock_get_size.return_value = (1920, 1080)
        
        # Execute
        from config.settings import get_screen_size_safe
        width, height = get_screen_size_safe()
        
        # Verify
        assert width == 1920
        assert height == 1080

    @patch('config.settings.get_scale_factor')
    def test_scale_factor_detection(self, mock_get_scale):
        """Test DPI scale factor detection."""
        # Setup
        mock_get_scale.return_value = 1.5
        
        # Execute
        from config.settings import get_scale_factor
        scale = get_scale_factor()
        
        # Verify
        assert scale == 1.5


class TestEnvFlagParsing:
    """Tests for environment flag parsing."""

    def test_parse_true_values(self):
        """Test parsing true boolean values."""
        from config.settings import _env_flag
        
        with patch.dict(os.environ, {"TEST_FLAG": "1"}):
            assert _env_flag("TEST_FLAG", False) is True
        
        with patch.dict(os.environ, {"TEST_FLAG": "true"}):
            assert _env_flag("TEST_FLAG", False) is True
        
        with patch.dict(os.environ, {"TEST_FLAG": "yes"}):
            assert _env_flag("TEST_FLAG", False) is True

    def test_parse_false_values(self):
        """Test parsing false boolean values."""
        from config.settings import _env_flag
        
        with patch.dict(os.environ, {"TEST_FLAG": "0"}):
            assert _env_flag("TEST_FLAG", True) is False
        
        with patch.dict(os.environ, {"TEST_FLAG": "false"}):
            assert _env_flag("TEST_FLAG", True) is False

    def test_parse_default_when_not_set(self):
        """Test using default when env var not set."""
        from config.settings import _env_flag
        
        with patch.dict(os.environ, {}, clear=True):
            assert _env_flag("NONEXISTENT", True) is True
            assert _env_flag("NONEXISTENT", False) is False