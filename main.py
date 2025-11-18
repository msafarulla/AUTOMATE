from functools import wraps
from typing import Callable, Any
from operations.inbound.receive import ReceiveOperation
from operations.outbound.loading import LoadingOperation
from ui.rf_menu import RFMenuManager
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


class WorkflowStageExecutor:
    def __init__(
        self,
        settings: Settings,
        orchestrator: AutomationOrchestrator,
        run_post_message: Callable[[str | None], bool],
        receive_fn: Callable[..., bool],
        loading_fn: Callable[..., bool],
    ):
        self.settings = settings
        self.orchestrator = orchestrator
        self.run_post_message = run_post_message
        self.receive_fn = receive_fn
        self.loading_fn = loading_fn
        self.stage_handlers = {
            "post": self.handle_post_stage,
            "receive": self.handle_receive_stage,
            "loading": self.handle_loading_stage,
        }

    def _confirm_prod_post(self, workflow_index: int) -> bool:
        if not self.settings.app.requires_prod_confirmation:
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

    def handle_post_stage(
        self, stage_cfg: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> tuple[dict[str, Any], bool]:
        if not bool(stage_cfg.get("enabled")):
            return metadata, True
        post_type = stage_cfg.get("type")
        if not post_type:
            app_log(f"❌ Post workflow {workflow_idx} missing 'type'; halting.")
            return metadata, False
        source = (stage_cfg.get("source") or "db").lower()
        db_env = stage_cfg.get("db_env")
        if not self._confirm_prod_post(workflow_idx):
            return metadata, False
        payload_metadata: dict[str, Any] = {}
        message_payload = None
        if source == "db":
            message_payload, payload_metadata = build_post_message_payload(
                stage_cfg,
                post_type,
                self.settings.app.change_warehouse,
                db_env,
            )
        else:
            message_payload = stage_cfg.get("message") or self.settings.app.post_message_text
        if not message_payload:
            app_log(
                f"❌ Unable to resolve post message payload for workflow {workflow_idx}; halting."
            )
            return metadata, False
        post_result = self.orchestrator.run_with_retry(
            lambda payload=message_payload: self.run_post_message(payload),
            f"Post Message (Workflow {workflow_idx})",
        )
        if not post_result.success:
            app_log(f"⏹️ Halting workflow {workflow_idx} due to post message failure")
            return metadata, False
        metadata.update(payload_metadata)
        return metadata, True

    def handle_receive_stage(
        self, stage_cfg: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> tuple[dict[str, Any], bool]:
        if not stage_cfg:
            return metadata, True
        override_asn = metadata.get("asn_id")
        receive_asn = override_asn if override_asn else stage_cfg.get("asn")
        receive_items = metadata.get("receive_items") or []
        receive_default = receive_items[0] if receive_items else {}
        receive_item = stage_cfg.get("item") or receive_default.get("item")
        quantity_cfg = stage_cfg.get("quantity", 0)
        receive_quantity = quantity_cfg if quantity_cfg else receive_default.get("quantity")
        if receive_quantity is None:
            receive_quantity = 1
        receive_result = self.orchestrator.run_with_retry(
            self.receive_fn,
            f"Receive (Workflow {workflow_idx})",
            asn=receive_asn,
            item=receive_item,
            quantity=receive_quantity,
            flow_hint=stage_cfg.get("flow"),
            auto_handle=stage_cfg.get("auto_handle_deviation", False),
        )
        if not receive_result.success:
            app_log(f"⏹️ Halting workflow {workflow_idx} due to receive failure")
            return metadata, False
        return metadata, True

    def handle_loading_stage(
        self, stage_cfg: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> tuple[dict[str, Any], bool]:
        if not stage_cfg:
            return metadata, True
        load_result = self.orchestrator.run_with_retry(
            self.loading_fn,
            f"Load (Workflow {workflow_idx})",
            shipment=stage_cfg.get("shipment"),
            dock_door=stage_cfg.get("dock_door"),
            bol=stage_cfg.get("bol"),
        )
        if not load_result.success:
            app_log(f"⏹️ Halting workflow {workflow_idx} due to loading failure")
            return metadata, False
        return metadata, True

    def run_stage(
        self, stage_name: str, stage_cfg: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> tuple[dict[str, Any], bool]:
        handler = self.stage_handlers.get(stage_name)
        if handler:
            return handler(stage_cfg, metadata, workflow_idx)
        app_log(f"ℹ️ No handler for workflow stage '{stage_name}'; skipping.")
        return metadata, True


def main():
    settings = Settings.from_env()
    with BrowserManager(settings) as browser_mgr:
        page = browser_mgr.new_page()

        screenshot_mgr = ScreenshotManager(
            settings.browser.screenshot_dir,
            image_format=settings.browser.screenshot_format,
            image_quality=settings.browser.screenshot_quality,
        )
        page_mgr = PageManager(page)
        auth_mgr = AuthManager(page, screenshot_mgr, settings)
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
            auth_mgr.login()

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

        stage_executor = WorkflowStageExecutor(
            settings,
            orchestrator,
            run_post_message,
            receive,
            loading,
        )

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

                workflow_metadata: dict[str, Any] = {}
                for stage_name, stage_cfg in workflow.items():
                    stage_cfg = stage_cfg or {}
                    workflow_metadata, continue_run = stage_executor.run_stage(
                        stage_name, stage_cfg, workflow_metadata, index
                    )
                    if not continue_run:
                        break

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
