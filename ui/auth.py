from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from utils.eval_utils import safe_page_evaluate
from core.screenshot import ScreenshotManager
from core.logger import app_log
from DB import DB
from config.settings import Settings


class AuthManager:
    def __init__(self, page: Page, screenshot_mgr: ScreenshotManager, settings: Settings, credentials_env: str = "qa"):
        self.page = page
        self.screenshot_mgr = screenshot_mgr
        self.credentials_env = credentials_env
        self._credentials: dict[str, str] | None = None
        self.settings = settings

    def login(self):
        base_url = self.settings.app.app_server
        self.page.goto(base_url, wait_until="networkidle")
        self.page.wait_for_selector("#username", timeout=5000)

        credentials = self._get_credentials()
        app_log("Filling username...")
        self.page.fill('#username', credentials["app_server_user"])

        app_log("Filling password...")
        self.page.fill('#password', credentials["app_server_pass"])

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
        self.page.wait_for_timeout(10000)

        if self.settings.app.auto_close_post_login_windows:
            self._close_default_windows()
        else:
            app_log("ℹ️ Skipping auto-close of post-login windows (disabled via settings).")
        self.screenshot_mgr.capture(self.page, "logged_in", "Logged In")
        app_log("✅ Logged in successfully")

    def _get_credentials(self) -> dict[str, str]:
        if self._credentials is None:
            self._credentials = DB.get_credentials(self.credentials_env)
        return self._credentials

    """Auto-Launch Menu can create default windows to open up, close them https://moshort.short.gy/gmHTsp"""
    def _close_default_windows(self):
        closed = 0
        try:
            try:
                self.page.wait_for_selector("div.x-window:visible", timeout=10000)
            except PlaywrightTimeoutError:
                app_log("ℹ️ No post-login windows detected.")
                return

            for _ in range(5):
                windows = self.page.locator("div.x-window:visible")
                count = windows.count()
                if count == 0:
                    break

                window_word = "windows" if count > 1 else "window"
                app_log(f"⚠️ Detected {count} post-login {window_word}; attempting to close.")
                self.screenshot_mgr.capture(self.page, "Default Windows", "Default Windows, will be closed")

                try:
                    close_btn = windows.first.locator(".x-tool-close").first
                    if close_btn.is_visible():
                        close_btn.click()
                        closed += 1
                        self.page.wait_for_timeout(200)
                        continue
                except Exception:
                    pass

                try:
                    self.page.keyboard.press("Escape")
                    closed += 1
                    self.page.wait_for_timeout(200)
                except Exception:
                    break

            if closed:
                app_log(f"✅ Closed {closed} post-login {'windows' if closed > 1 else 'window'}.")
            else:
                app_log("ℹ️ No post-login windows required closing.")
        except Exception as exc:
            app_log(f"⚠️ Failed closing post-login windows: {exc}")
