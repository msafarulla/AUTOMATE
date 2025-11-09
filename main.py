from operations.inbound.receive import ReceiveOperation
from ui.rf_menu import RFMenuManager
from DB import DB
from config.settings import Settings
from core.browser import BrowserManager
from core.page_manager import PageManager
from core.screenshot import ScreenshotManager
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


        try:
            # Login and setup
            auth_mgr.login(username, password, settings.app.base_url)
            nav_mgr.change_warehouse(settings.app.change_warehouse)

            while 1:
                # # Launch Post Message screen oh
                # nav_mgr.open_menu_item("POST", "Post Message (Integration)")
                # # Send the payload with a built-in retry before moving on
                # success, response_info = post_message_mgr.send_message(settings.app.post_message_text)
                # print(f"Response summary: {response_info['summary']}")
                # if response_info.get("payload"):
                #     print(f"Response payload: {response_info['payload']}")
                # if not success:
                #     print("⚠️ Post Message failed; continuing with the remaining flow.")

                nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
                receive_op = ReceiveOperation(page, page_mgr, screenshot_mgr, rf_menu)
                receive_op.execute(asn='23907432', item='J105SXC200TR', quantity=1)

            input("Press Enter to exit...")
        except Exception as e:
            print(f"Error in main flow: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()


🧹 Closing window: RF Menu
Error in main flow: Locator.click: Timeout 30000ms exceeded.
Call log:
  - waiting for locator("a.x-btn").first
    - locator resolved to <a tabindex="-1" hidefocus="on" id="button-1013" unselectable="on" data-savedtabindex="0" componentid="button-1013" data-tabindexsaved="true" class="x-btn x-unselectable x-box-item x-toolbar-item x-btn-default-toolbar-medium">…</a>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div role="presentation" id="ext-element-86" class="x-mask x-mask-fixed"></div> intercepts pointer events
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div role="presentation" id="ext-element-86" class="x-mask x-mask-fixed"></div> intercepts pointer events
    - retrying click action
      - waiting 100ms
    56 × waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <div role="presentation" id="ext-element-86" class="x-mask x-mask-fixed"></div> intercepts pointer events
     - retrying click action
       - waiting 500ms

Traceback (most recent call last):
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\main.py", line 55, in main
    nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\ui\navigation.py", line 69, in open_menu_item
    self._open_menu_panel()
    ~~~~~~~~~~~~~~~~~~~~~^^
  File "E:\dnt\chihu\home\vxmsafar\AUTOMATE\ui\navigation.py", line 123, in _open_menu_panel
    page.locator("a.x-btn").first.click()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
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
  - waiting for locator("a.x-btn").first
    - locator resolved to <a tabindex="-1" hidefocus="on" id="button-1013" unselectable="on" data-savedtabindex="0" componentid="button-1013" data-tabindexsaved="true" class="x-btn x-unselectable x-box-item x-toolbar-item x-btn-default-toolbar-medium">…</a>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div role="presentation" id="ext-element-86" class="x-mask x-mask-fixed"></div> intercepts pointer events
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div role="presentation" id="ext-element-86" class="x-mask x-mask-fixed"></div> intercepts pointer events
    - retrying click action
      - waiting 100ms
    56 × waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <div role="presentation" id="ext-element-86" class="x-mask x-mask-fixed"></div> intercepts pointer events
     - retrying click action
       - waiting 500ms


