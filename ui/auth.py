from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from utils.eval_utils import safe_page_evaluate
from core.screenshot import ScreenshotManager
from core.logger import app_log
from DB import DB
from config.settings import Settings
from utils.wait_utils import WaitUtils


class AuthManager:
    def __init__(self, page: Page, screenshot_mgr: ScreenshotManager, settings: Settings, credentials_env: str | None = None):
        self.page = page
        self.screenshot_mgr = screenshot_mgr
        self.credentials_env = credentials_env or settings.app.credentials_env
        self._credentials: dict[str, str] | None = None
        self.settings = settings

    def login(self):
        base_url = self.settings.app.app_server
        app_log(f"🌐 Navigating to login page: {base_url} (creds env={self.credentials_env})")
        self.page.goto(base_url, wait_until="networkidle")
        self.page.wait_for_selector("#username", timeout=10000)
        self.page.wait_for_selector("#password", timeout=10000)

        credentials = self._get_credentials()
        app_log(f"Using credentials for user: {credentials.get('app_server_user')}")
        
        # Fill credentials efficiently
        app_log("Filling username...")
        self.page.locator('#username').fill(credentials["app_server_user"])

        app_log("Filling password...")
        self.page.locator('#password').fill(credentials["app_server_pass"])

        # Wait for login button to enable using efficient Playwright wait
        app_log("Waiting for login button to enable...")
        try:
            self.page.wait_for_function(
                "!document.getElementById('loginButton').disabled",
                timeout=15000,
            )
        except PlaywrightTimeoutError:
            is_disabled = safe_page_evaluate(
                self.page,
                "(() => { const btn = document.getElementById('loginButton'); return btn ? btn.disabled : true; })()",
                description="AuthManager.is_login_disabled",
                suppress_log=True,
            )
            raise Exception(
                f"Login button did not enable within 15s (disabled={is_disabled})"
            )

        # Capture the form state just before attempting login
        self.screenshot_mgr.capture(self.page, "login_ready", f"Login form ready ({base_url})")

        app_log("Clicking login button...")
        nav_succeeded = False
        try:
            with self.page.expect_navigation(wait_until="networkidle", timeout=30000):
                self.page.click('#loginButton')
            nav_succeeded = True
        except PlaywrightTimeoutError:
            app_log("⚠️ Login click did not navigate; retrying with Enter...")
            try:
                with self.page.expect_navigation(wait_until="networkidle", timeout=20000):
                    self.page.keyboard.press("Enter")
                nav_succeeded = True
            except PlaywrightTimeoutError as exc:
                self.screenshot_mgr.capture(self.page, "login_failed", "Login did not navigate")
                raise Exception("Login click/Enter did not trigger navigation") from exc

        if not nav_succeeded:
            self.screenshot_mgr.capture(self.page, "login_failed", "Login did not navigate")
            raise Exception("Login flow ended without navigation")

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
                        WaitUtils.wait_brief(self.page, timeout_ms=300)
                        continue
                except Exception:
                    pass

                try:
                    self.page.keyboard.press("Escape")
                    closed += 1
                    WaitUtils.wait_brief(self.page, timeout_ms=300)
                except Exception:
                    break

            if closed:
                app_log(f"✅ Closed {closed} post-login {'windows' if closed > 1 else 'window'}.")
            else:
                app_log("ℹ️ No post-login windows required closing.")
        except Exception as exc:
            app_log(f"⚠️ Failed closing post-login windows: {exc}")