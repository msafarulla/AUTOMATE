"""
Updated main.py showing how to use both old and new operations side-by-side.

You can gradually migrate operations one at a time without breaking anything!
"""
from operations.inbound.receive import ReceiveOperation  # Old version
from operations.inbound.receive_refactored import ReceiveOperationRefactored  # New version
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
        rf_menu = RFMenuManager(page, page_mgr, screenshot_mgr)
        conn_guard = ConnectionResetGuard(page, screenshot_mgr)

        def run_receive_cycle_old():
            """Use the OLD receive operation (still works!)"""
            nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
            receive_op = ReceiveOperation(page, page_mgr, screenshot_mgr, rf_menu)
            receive_op.execute(asn='23907432', item='J105SXC200TR', quantity=1)

        def run_receive_cycle_new():
            """Use the NEW refactored receive operation (much cleaner!)"""
            nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
            receive_op = ReceiveOperationRefactored(page, page_mgr, screenshot_mgr, rf_menu)
            receive_op.execute(asn='23907432', item='J105SXC200TR', quantity=1)

        try:
            # Login and setup
            conn_guard.guard(auth_mgr.login, username, password, settings.app.base_url)
            conn_guard.guard(nav_mgr.change_warehouse, settings.app.change_warehouse)

            # Choose which version to use:
            # Option 1: Use old version (still works)
            # conn_guard.guard(run_receive_cycle_old)

            # Option 2: Use new refactored version (recommended!)
            while 1:
                conn_guard.guard(run_receive_cycle_new)

            print("✅ Operation completed successfully!")
            input("Press Enter to exit...")

        except ConnectionResetDetected as e:
            print(f"❌ Halting run: {e}")
        except Exception as e:
            print(f"Error in main flow: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()



✅ Exact match found: 'RF Menu (Distribution)' — selecting it
Error in main flow: Locator.click: Timeout 30000ms exceeded.
Call log:
  - waiting for locator("ul.x-list-plain:visible li.x-boundlist-item").first

Traceback (most recent call last):
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\main.py", line 69, in main
    conn_guard.guard(run_receive_cycle_new)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\core\connection_guard.py", line 45, in guard
    result = func(*args, **kwargs)
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\main.py", line 54, in run_receive_cycle_new
    nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\ui\navigation.py", line 99, in open_menu_item
    self._activate_menu_selection(items.nth(i), "rf menu" in normalized_match)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\ui\navigation.py", line 320, in _activate_menu_selection
    item_locator.click()
    ~~~~~~~~~~~~~~~~~~^^
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\.venv\Lib\site-packages\playwright\sync_api\_generated.py", line 15543, in click
    self._sync(
    ~~~~~~~~~~^
        self._impl_obj.click(
        ^^^^^^^^^^^^^^^^^^^^^
    ...<9 lines>...
        )
        ^
    )
    ^
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\.venv\Lib\site-packages\playwright\_impl\_sync_base.py", line 115, in _sync
    return task.result()
           ~~~~~~~~~~~^^
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\.venv\Lib\site-packages\playwright\_impl\_locator.py", line 160, in click
    return await self._frame.click(self._selector, strict=True, **params)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\.venv\Lib\site-packages\playwright\_impl\_frame.py", line 549, in click
    await self._channel.send("click", self._timeout, locals_to_params(locals()))
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\.venv\Lib\site-packages\playwright\_impl\_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<3 lines>...
    )
    ^
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\.venv\Lib\site-packages\playwright\_impl\_connection.py", line 558, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.
Call log:
  - waiting for locator("ul.x-list-plain:visible li.x-boundlist-item").first

