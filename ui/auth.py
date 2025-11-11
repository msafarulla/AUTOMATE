from playwright.sync_api import Page
from utils.eval_utils import safe_page_evaluate
from core.screenshot import ScreenshotManager
from core.logger import app_log


class AuthManager:
    def __init__(self, page: Page, screenshot_mgr: ScreenshotManager):
        self.page = page
        self.screenshot_mgr = screenshot_mgr

    def login(self, username: str, password: str, base_url: str):
        self.page.goto(base_url, wait_until="networkidle")
        self.page.wait_for_selector("#username", timeout=5000)

        app_log("Filling username...")
        self.page.fill('#username', username)

        app_log("Filling password...")
        self.page.fill('#password', password)

        app_log("Dispatching events...")
        self.page.dispatch_event('#username', 'input')
        self.page.dispatch_event('#password', 'input')
        self.page.dispatch_event('#username', 'keyup')
        self.page.dispatch_event('#password', 'keyup')

        app_log("Waiting for button to be enabled...")
        self.page.wait_for_timeout(2000)

        # Verify button is enabled before clicking
        is_disabled = safe_page_evaluate(self.page,
                                         "document.getElementById('loginButton').disabled",
                                         description="AuthManager.is_login_disabled")
        if is_disabled:
            raise Exception("Login button is still disabled after filling credentials")

        app_log("Clicking login button...")
        self.page.click('#loginButton')
        self.page.wait_for_timeout(5000)

        self.screenshot_mgr.capture(self.page, "logged_in", "Logged In")
        app_log("✅ Logged in successfully")
