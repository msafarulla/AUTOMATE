from typing import Any, Tuple

from core.logger import app_log
from core.orchestrator import AutomationOrchestrator
from core.post_message_payload import build_post_message_payload
from config.settings import Settings
from operations.runner import StepExecution


class WorkflowStageExecutor:
    def __init__(
        self,
        settings: Settings,
        orchestrator: AutomationOrchestrator,
        step_execution: StepExecution,
    ):
        self.settings = settings
        self.orchestrator = orchestrator
        self.step_execution = step_execution
        self.step_handlers = {
            "post": self.handle_post_stage,
            "receive": self.handle_receive_stage,
            "loading": self.handle_loading_stage,
            "tasks": self.handle_tasks_stage,
            "ilpns": self.handle_ilpns_stage,
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
    ) -> Tuple[dict[str, Any], bool]:
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
            message_payload = (
                stage_cfg.get("message") or self.settings.app.post_message_text
            )
        if not message_payload:
            app_log(
                f"❌ Unable to resolve post message payload for workflow {workflow_idx}; halting."
            )
            return metadata, False
        post_result = self.orchestrator.run_with_retry(
            lambda payload=message_payload: self.step_execution.run_post_message(
                payload
            ),
            f"Post Message (Workflow {workflow_idx})",
        )
        if not post_result.success:
            app_log(f"⏹️ Halting workflow {workflow_idx} due to post message failure")
            return metadata, False
        metadata.update(payload_metadata)
        return metadata, True

    def handle_receive_stage(
        self, stage_cfg: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> Tuple[dict[str, Any], bool]:
        if not stage_cfg:
            return metadata, True
        override_asn = metadata.get("asn_id")
        receive_asn = override_asn if override_asn else stage_cfg.get("asn")
        receive_items = metadata.get("receive_items") or []
        receive_default = receive_items[0] if receive_items else {}
        receive_item = stage_cfg.get("item") or receive_default.get("item")
        quantity_cfg = stage_cfg.get("quantity", 0)
        receive_quantity = (
            quantity_cfg if quantity_cfg else receive_default.get("quantity")
        )
        if receive_quantity is None:
            receive_quantity = 1
        # Support either legacy "tasks" detour or the newer "ilpns" config
        open_ui_cfg = (
            stage_cfg.get("open_ui")
            or stage_cfg.get("tasks")
            or stage_cfg.get("ilpns")
        )
        receive_result = self.orchestrator.run_with_retry(
            self.step_execution.receive,
            f"Receive (Workflow {workflow_idx})",
            asn=receive_asn,
            item=receive_item,
            quantity=receive_quantity,
            flow_hint=stage_cfg.get("flow"),
            auto_handle=stage_cfg.get("auto_handle_deviation", False),
            open_ui_cfg=open_ui_cfg,
        )
        if not receive_result.success:
            app_log(f"⏹️ Halting workflow {workflow_idx} due to receive failure")
            return metadata, False
        return metadata, True

    def handle_loading_stage(
        self, stage_cfg: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> Tuple[dict[str, Any], bool]:
        if not stage_cfg:
            return metadata, True
        load_result = self.orchestrator.run_with_retry(
            self.step_execution.loading,
            f"Load (Workflow {workflow_idx})",
            shipment=stage_cfg.get("shipment"),
            dock_door=stage_cfg.get("dock_door"),
            bol=stage_cfg.get("bol"),
        )
        if not load_result.success:
            app_log(f"⏹️ Halting workflow {workflow_idx} due to loading failure")
            return metadata, False
        return metadata, True

    def handle_tasks_stage(
        self, stage_cfg: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> Tuple[dict[str, Any], bool]:
        if not bool(stage_cfg.get("enabled", True)):
            return metadata, True
        search_term = stage_cfg.get("search_term", "tasks")
        match_text = stage_cfg.get("match_text", "Tasks (Configuration)")
        in_place = bool(stage_cfg.get("preserve_window") or stage_cfg.get("preserve"))
        if in_place:
            success = self.step_execution.run_tasks_ui_in_place(search_term, match_text)
        else:
            success = self.step_execution.run_tasks_ui(search_term, match_text)
        if not success:
            app_log(f"❌ Unable to open Tasks UI for workflow {workflow_idx}; halting.")
            return metadata, False
        return metadata, True

    def handle_ilpns_stage(
        self, stage_cfg: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> Tuple[dict[str, Any], bool]:
        if not bool(stage_cfg.get("enabled", True)):
            return metadata, True
        search_term = stage_cfg.get("search_term", "ilpns")
        match_text = stage_cfg.get("match_text", "iLPNs (Distribution)")
        in_place = bool(stage_cfg.get("preserve_window") or stage_cfg.get("preserve"))
        if in_place:
            success = self.step_execution.run_tasks_ui_in_place(search_term, match_text)
        else:
            success = self.step_execution.run_tasks_ui(search_term, match_text)
        if not success:
            app_log(f"❌ Unable to open iLPNs UI for workflow {workflow_idx}; halting.")
            return metadata, False
        return metadata, True


    def run_step(
        self,
        stage_name: str,
        stage_cfg: dict[str, Any],
        metadata: dict[str, Any],
        workflow_idx: int,
    ) -> Tuple[dict[str, Any], bool]:
        handler = self.step_handlers.get(stage_name.lower())
        if handler:
            return handler(stage_cfg, metadata, workflow_idx)
        app_log(f"ℹ️ No handler for workflow stage '{stage_name}'; skipping.")
        return metadata, True
