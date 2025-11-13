"""
Main entry point for warehouse automation with orchestration, retries, and summaries.
"""
from functools import wraps
from typing import Callable, Any

from operations.inbound.receive import ReceiveOperation
from operations.outbound.loading import LoadingOperation
from ui.rf_menu import RFMenuManager
from DB import DB
from config.settings import Settings
from config.operations_config import OperationConfig
from core.browser import BrowserManager
from core.page_manager import PageManager
from core.screenshot import ScreenshotManager
from core.connection_guard import ConnectionResetGuard, ConnectionResetDetected
from ui.auth import AuthManager
from ui.navigation import NavigationManager
from ui.post_message import PostMessageManager
from core.logger import app_log
from core.orchestrator import AutomationOrchestrator


def main():
    """Main entry point with improved orchestration."""
    settings = Settings.from_env()

    with DB('qa') as c1:
        username = c1.app_server_user
        password = c1.app_server_pass

    with BrowserManager(settings) as browser_mgr:
        page = browser_mgr.new_page()

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
        orchestrator = AutomationOrchestrator(settings, max_retries=3)

        def guarded(func: Callable):
            """Decorator to run helpers inside the connection guard."""
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any):
                return conn_guard.guard(func, *args, **kwargs)

            return wrapper

        @guarded
        def run_login():
            auth_mgr.login(username, password, settings.app.base_url)

        @guarded
        def run_change_warehouse():
            nav_mgr.change_warehouse(settings.app.change_warehouse)

        @guarded
        def receive(asn: str, item: str, quantity: int = 1) -> bool:
            nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
            receive_op = ReceiveOperation(page, page_mgr, screenshot_mgr, rf_menu)
            return receive_op.execute(asn, item, quantity)

        @guarded
        def loading(shipment: str, dock_door: str, bol: str) -> bool:
            nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
            load_op = LoadingOperation(page, page_mgr, screenshot_mgr, rf_menu)
            return load_op.execute(shipment, dock_door, bol)

        @guarded
        def run_post_message():
            nav_mgr.open_menu_item("POST", "Post Message (Integration)")
            success, response_info = post_message_mgr.send_message(settings.app.post_message_text)
            app_log(f"Response summary: {response_info['summary']}")
            if response_info.get("payload"):
                app_log(f"Response payload: {response_info['payload']}")
            if not success:
                app_log("⚠️ Post Message failed; continuing with remaining flow.")
            return success

        try:
            app_log("🚀 Starting warehouse automation...")
            run_login()
            run_change_warehouse()

            workflows = OperationConfig.DEFAULT_WORKFLOWS

            for index, workflow in enumerate(workflows, 1):
                app_log("\n" + "=" * 60)
                app_log(f"📦 WORKFLOW {index}/{len(workflows)}")
                app_log("=" * 60)

                post_cfg = workflow.get('post', {})
                if post_cfg.get('enabled'):
                    orchestrator.run_with_retry(
                        run_post_message,
                        f"Post Message (Workflow {index})"
                    )

                receive_cfg = workflow.get('receive')
                receive_result = None
                if receive_cfg:
                    receive_result = orchestrator.run_with_retry(
                        receive,
                        f"Receive (Workflow {index})",
                        asn=receive_cfg['asn'],
                        item=receive_cfg['item'],
                        quantity=receive_cfg.get('quantity', 1)
                    )

                loading_cfg = workflow.get('loading')
                if loading_cfg and (receive_result is None or receive_result.success):
                    orchestrator.run_with_retry(
                        loading,
                        f"Loading (Workflow {index})",
                        shipment=loading_cfg['shipment'],
                        dock_door=loading_cfg['dock_door'],
                        bol=loading_cfg['bol']
                    )
                elif loading_cfg:
                    app_log(f"⏭️ Skipping loading for workflow {index} due to receive failure")

            orchestrator.print_summary()
            app_log("✅ Automation completed!")
            input("Press Enter to exit...")

        except ConnectionResetDetected as exc:
            app_log(f"❌ Connection lost: {exc}")
            orchestrator.print_summary()
        except KeyboardInterrupt:
            app_log("\n⚠️ Interrupted by user")
            orchestrator.print_summary()
        except Exception as exc:
            app_log(f"❌ Fatal error in main flow: {exc}")
            import traceback
            traceback.print_exc()
            orchestrator.print_summary()


if __name__ == "__main__":
    main()
