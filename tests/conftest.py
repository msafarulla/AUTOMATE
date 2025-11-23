"""
Pytest configuration and shared fixtures.
"""
import pytest
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass


@dataclass
class MockFrame:
    """Mock Playwright Frame for testing."""
    _text: str = ""
    _is_detached: bool = False

    def locator(self, selector: str):
        mock = MagicMock()
        mock.inner_text.return_value = self._text
        mock.first = mock
        mock.wait_for = MagicMock()
        mock.fill = MagicMock()
        mock.press = MagicMock()
        mock.count.return_value = 1
        return mock

    def is_detached(self) -> bool:
        return self._is_detached

    @property
    def url(self) -> str:
        return "http://test/RFMenu"

    @property
    def name(self) -> str:
        return "uxiframe_rf"


@dataclass
class MockPage:
    """Mock Playwright Page for testing."""
    _frame: MockFrame | None = None

    def __post_init__(self):
        if self._frame is None:
            self._frame = MockFrame()

    @property
    def frames(self) -> list[MockFrame]:
        return [self._frame]

    @property
    def main_frame(self):
        return self._frame

    def locator(self, selector: str):
        return self._frame.locator(selector)

    def wait_for_timeout(self, ms: int):
        pass

    def keyboard(self):
        mock = MagicMock()
        mock.press = MagicMock()
        return mock

    def evaluate(self, script, arg=None):
        return None


@pytest.fixture
def mock_frame():
    """Provide a mock Frame."""
    return MockFrame()


@pytest.fixture
def mock_page(mock_frame):
    """Provide a mock Page."""
    return MockPage(_frame=mock_frame)


@pytest.fixture
def mock_screenshot_mgr():
    """Provide a mock ScreenshotManager."""
    mgr = MagicMock()
    mgr.capture_rf_window = MagicMock(return_value=None)
    mgr.capture = MagicMock(return_value=None)
    mgr.set_scenario = MagicMock()
    mgr.set_stage = MagicMock()
    return mgr


@pytest.fixture
def mock_rf_primitives(mock_page, mock_screenshot_mgr):
    """Provide mock RF primitives."""
    from operations.rf_primitives import RFPrimitives

    primitives = MagicMock(spec=RFPrimitives)
    primitives.page = mock_page
    primitives.screenshot_mgr = mock_screenshot_mgr
    primitives.get_iframe = MagicMock(return_value=mock_page.main_frame)
    primitives.fill_and_submit = MagicMock(return_value=(False, None))
    primitives.read_field = MagicMock(return_value="")
    primitives.press_key = MagicMock()
    primitives.go_home = MagicMock()
    primitives.accept_message = MagicMock()
    primitives._should_auto_accept = MagicMock(return_value=True)

    return primitives


@pytest.fixture
def mock_rf_workflows(mock_rf_primitives):
    """Provide mock RF workflows."""
    from operations.rf_primitives import RFWorkflows

    workflows = MagicMock(spec=RFWorkflows)
    workflows.rf = mock_rf_primitives
    workflows.navigate_to_menu_by_search = MagicMock(return_value=True)
    workflows.scan_barcode_auto_enter = MagicMock(return_value=(False, None))
    workflows.enter_quantity = MagicMock(return_value=True)
    workflows.confirm_location = MagicMock(return_value=(False, None))

    return workflows