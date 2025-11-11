from operations.inbound.receive import ReceiveOperation
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

        def run_receive_cycle():
            nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
            receive_op = ReceiveOperation(page, page_mgr, screenshot_mgr, rf_menu)
            receive_op.execute(asn='23907432', item='J105SXC200TR', quantity=1)

        try:
            # Login and setup
            conn_guard.guard(auth_mgr.login, username, password, settings.app.base_url)
            conn_guard.guard(nav_mgr.change_warehouse, settings.app.change_warehouse)

            while 1:
                # # Launch Post Message screen oh
                # nav_mgr.open_menu_item("POST", "Post Message (Integration)")
                # # Send the payload with a built-in retry before moving on
                # success, response_info = post_message_mgr.send_message(settings.app.post_message_text)
                # # DEBUG: Response summary/payload logging removed; use app_log if needed.
                # # if not success:
                # #     app_log("⚠️ Post Message failed; continuing with the remaining flow.")

                conn_guard.guard(run_receive_cycle)

            input("Press Enter to exit...")
        except ConnectionResetDetected as e:
            app_log(f"❌ Halting run: {e}")
        except Exception as e:
            app_log(f"Error in main flow: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
