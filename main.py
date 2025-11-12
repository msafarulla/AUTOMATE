from functools import wraps
from operations.inbound.receive_refactored import ReceiveOperationRefactored
from operations.outbound.loading import LoadingOperation
from ui.rf_menu import RFMenuManager
from DB import DB
from config.settings import Settings
from core.browser import BrowserManager
from core.page_manager import PageManager
from core.screenshot import ScreenshotManager
from core.connection_guard import ConnectionResetGuard, ConnectionResetDetected
from ui.auth import AuthManager
from ui.navigation import NavigationManager
from ui.post_message import PostMessageManager
from core.logger import app_log
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


def main():
    # Load configuration
    settings = Settings.from_env()

    # Load credentials
    with DB('qa') as c1:
        username = c1.app_server_user
        password = c1.app_server_pass

    # Initialize browser
    with BrowserManager(settings) as browser_mgr:
        page = browser_mgr.new_page()

        # Initialize managers
        screenshot_mgr = ScreenshotManager(
            settings.browser.screenshot_dir,
            image_format=settings.browser.screenshot_format,
            image_quality=settings.browser.screenshot_quality,
        )
        page_mgr = PageManager(page)
        auth_mgr = AuthManager(page, screenshot_mgr)
        nav_mgr = NavigationManager(page, screenshot_mgr)
        post_message_mgr = PostMessageManager(page, screenshot_mgr)
        rf_menu = RFMenuManager(
            page,
            page_mgr,
            screenshot_mgr,
            verbose_logging=settings.app.rf_verbose_logging,
        )
        conn_guard = ConnectionResetGuard(page, screenshot_mgr)

        def guarded(func):
            """Decorator to automatically run handlers inside the connection guard."""
            @wraps(func)
            def wrapper(*args, **kwargs):
                return conn_guard.guard(func, *args, **kwargs)

            return wrapper

        def close_post_login_windows():
            """Close any popup windows that appear immediately after sign-on."""
            closed = 0
            try:
                try:
                    page.wait_for_selector("div.x-window:visible", timeout=4000)
                except PlaywrightTimeoutError:
                    app_log("ℹ️ No post-login windows detected.")
                    return False

                for _ in range(5):
                    windows = page.locator("div.x-window:visible")
                    count = windows.count()
                    if count == 0:
                        break

                    window_word = "windows" if count > 1 else "window"
                    app_log(f"⚠️ Detected {count} post-login {window_word}; attempting to close.")

                    try:
                        close_btn = windows.first.locator(".x-tool-close").first
                        if close_btn.is_visible():
                            close_btn.click()
                            closed += 1
                            page.wait_for_timeout(200)
                            continue
                    except Exception:
                        pass

                    try:
                        page.keyboard.press("Escape")
                        closed += 1
                        page.wait_for_timeout(200)
                    except Exception:
                        break

                if closed:
                    app_log(f"✅ Closed {closed} post-login {'windows' if closed > 1 else 'window'}.")
                else:
                    app_log("ℹ️ No post-login windows required closing.")

                return closed > 0
            except Exception as exc:
                app_log(f"⚠️ Failed closing post-login windows: {exc}")
                return False

        @guarded
        def run_login():
            """Authenticate once per session inside the guard."""
            auth_mgr.login(username, password, settings.app.base_url)
            close_post_login_windows()

        @guarded
        def run_change_warehouse():
            """Switch warehouses safely inside the guard."""
            nav_mgr.change_warehouse(settings.app.change_warehouse)

        @guarded
        def run_receive_cycle():
            """Use the NEW refactored receive operation (much cleaner!)"""
            nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
            receive_op = ReceiveOperationRefactored(page, page_mgr, screenshot_mgr, rf_menu)
            receive_op.execute(asn='23907432', item='J105SXC200TR', quantity=1)

        @guarded
        def run_post_cycle():
            """Launch Post Message screen"""
            nav_mgr.open_menu_item("POST", "Post Message (Integration)")
            # Send the payload with a built-in retry before moving on
            success, response_info = post_message_mgr.send_message(settings.app.post_message_text)
            app_log(f"Response summary: {response_info['summary']}")
            if response_info.get("payload"):
                app_log(f"Response payload: {response_info['payload']}")
            if not success:
                app_log("⚠️ Post Message failed; continuing with the remaining flow.")

        @guarded
        def run_loading_cycle():
            """Use the NEW refactored receive operation (much cleaner!)"""
            nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
            load_op = LoadingOperation(page, page_mgr, screenshot_mgr, rf_menu)
            load_op.execute(shipment='23907432', dockDoor='J105SXC200TR', BOL='MOH')

        try:
            # Login and setup
            run_login()
            run_change_warehouse()

            # Choose which version to use:
            # Option 1: Use old version (still works)
            # conn_guard.guard(run_receive_cycle_old)

            # Option 2: Use new refactored version (recommended!)

            # run_post_cycle()
            while 1:
                run_receive_cycle()
                run_loading_cycle()

            app_log("✅ Operation completed successfully!")
            input("Press Enter to exit...")

        except ConnectionResetDetected as e:
            app_log(f"❌ Halting run: {e}")
        except Exception as e:
            app_log(f"Error in main flow: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
