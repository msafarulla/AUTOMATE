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
from core.post_message_payload import build_post_message_payload


def main():
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
            auto_click_info_icon=settings.app.auto_click_info_icon,
        )
        conn_guard = ConnectionResetGuard(page, screenshot_mgr)
        orchestrator = AutomationOrchestrator(settings)

        def guarded(func: Callable):
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
        def receive(
            asn: str,
            item: str,
            quantity: int = 1,
            flow_hint: str | None = None,
            auto_handle: bool = False,
        ) -> bool:
            nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
            receive_op = ReceiveOperation(page, page_mgr, screenshot_mgr, rf_menu)
            return receive_op.execute(
                asn,
                item,
                quantity,
                flow_hint=flow_hint,
                auto_handle=auto_handle,
            )

        @guarded
        def loading(shipment: str, dock_door: str, bol: str) -> bool:
            nav_mgr.open_menu_item("RF MENU", "RF Menu (Distribution)")
            load_op = LoadingOperation(page, page_mgr, screenshot_mgr, rf_menu)
            return load_op.execute(shipment, dock_door, bol)

        def _confirm_prod_post(workflow_index: int) -> bool:
            if not settings.app.requires_prod_confirmation:
                return True
            app_log(f"⚠️ Workflow {workflow_index}: about to send a PROD post message.")
            first = input("Type PROD to continue: ").strip().upper()
            if first != "PROD":
                app_log("❌ First confirmation failed; aborting PROD post.")
                return False
            second = input("Re-type PROD to confirm: ").strip().upper()
            if second != "PROD":
                app_log("❌ Second confirmation failed; aborting PROD post.")
                return False
            app_log("✅ PROD confirmation received.")
            return True

        @guarded
        def run_post_message(payload: str | None = None):
            nav_mgr.open_menu_item("POST", "Post Message (Integration)")
            message = payload or settings.app.post_message_text
            if not message:
                app_log("⚠️ No post message payload supplied.")
                return False
            success, response_info = post_message_mgr.send_message(message)
            app_log(f"Response summary: {response_info['summary']}")
            if response_info.get("payload"):
                app_log(f"Response payload: {response_info['payload']}")
            if not success:
                app_log("⚠️ Post Message failed.")
            return success

        try:
            app_log("🚀 Starting warehouse automation...")
            run_login()
            nav_mgr.close_menu_overlay_after_sign_on()
            run_change_warehouse()

            workflow_map = OperationConfig.DEFAULT_WORKFLOWS
            workflow_items = list(workflow_map.items())
            total_workflows = len(workflow_items)

            for index, (scenario_name, workflow) in enumerate(workflow_items, 1):
                screenshot_mgr.set_scenario(scenario_name)
                app_log("\n" + "=" * 60)
                app_log(f"📦 WORKFLOW {index}/{total_workflows} ({scenario_name})")
                app_log("=" * 60)

                post_cfg = workflow.get('post', {})
                payload_metadata: dict[str, Any] = {}
                post_result = None
                receive_cfg = workflow.get('receive')
                should_post = bool(post_cfg.get('enabled')) and not (receive_cfg and receive_cfg.get('asn'))
                if should_post:
                    post_type = post_cfg.get('type')
                    if not post_type:
                        app_log(f"❌ Post workflow {index} missing 'type'; halting.")
                        break

                    source = (post_cfg.get('source') or 'db').lower()
                    db_env = post_cfg.get('db_env')
                    if not _confirm_prod_post(index):
                        break
                    message_payload = None
                    if source == 'db':
                        message_payload, payload_metadata = build_post_message_payload(
                            post_cfg,
                            post_type,
                            settings.app.change_warehouse,
                            db_env
                        )
                    else:
                        message_payload = post_cfg.get('message') or settings.app.post_message_text

                    if not message_payload:
                        app_log(f"❌ Unable to resolve post message payload for workflow {index}; halting.")
                        break

                    post_result = orchestrator.run_with_retry(
                        lambda payload=message_payload: run_post_message(payload),
                        f"Post Message (Workflow {index})"
                    )
                    if not post_result.success:
                        app_log(f"⏹️ Halting workflow {index} due to post message failure")
                        break
                elif post_cfg.get('enabled'):
                    app_log(f"ℹ️ Skipping Post Message for workflow {index}; receive config supplied ASN.")

                receive_result = None
                if receive_cfg:
                    override_asn = payload_metadata.get('asn_id')
                    receive_asn = override_asn if override_asn else receive_cfg.get('asn')
                    receive_items = payload_metadata.get('receive_items') or []
                    receive_default = receive_items[0] if receive_items else {}
                    receive_item = receive_cfg.get('item') or receive_default.get('item')
                    quantity_cfg = receive_cfg.get('quantity', 0)
                    receive_quantity = quantity_cfg if quantity_cfg else receive_default.get('quantity')
                    if receive_quantity is None:
                        receive_quantity = 1
                    receive_result = orchestrator.run_with_retry(
                        receive,
                        f"Receive (Workflow {index})",
                        asn=receive_asn,
                        item=receive_item,
                        quantity=receive_quantity,
                        flow_hint=receive_cfg.get('flow'),
                        auto_handle=receive_cfg.get('auto_handle_deviation', False),
                    )

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
        finally:
            screenshot_mgr.set_scenario(None)


if __name__ == "__main__":
    main()
