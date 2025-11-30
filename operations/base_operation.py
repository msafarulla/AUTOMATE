from abc import ABC, abstractmethod
from playwright.sync_api import Page
from core.page_manager import PageManager
from core.screenshot import ScreenshotManager
from ui.rf_menu import RFMenuManager


class BaseOperation(ABC):
    def __init__(self, page: Page, page_mgr: PageManager, screenshot_mgr: ScreenshotManager, rf_menu: RFMenuManager):
        self.page = page
        self.page_mgr = page_mgr
        self.screenshot_mgr = screenshot_mgr
        self.rf_menu = rf_menu

    @abstractmethod
    def execute(self, *args, **kwargs) -> bool:
        """Execute the operation."""
        raise NotImplementedError("Subclasses must implement execute() and return a bool.")

    def handle_error_screen(self, rf_iframe):
        """Common error handling logic"""
        has_error, msg = self.rf_menu.check_for_response(rf_iframe)
        if msg:
            self.rf_menu.accept_proceed(rf_iframe)
            self.page.mouse.move(50, 50)
        return has_error, msg
