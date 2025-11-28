from typing import Any, Sequence, Tuple

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
        step_names = self.settings.app.step_names
        self.step_handlers = {
            step_names.postMessage.lower(): self.handle_post_step,
            step_names.runReceiving.lower(): self.handle_receive_step,
            step_names.runLoading.lower(): self.handle_loading_step,
            step_names.OpenTasksUi.lower(): self.handle_tasks_step,
            step_names.OpenIlpnUi.lower(): self.handle_ilpns_step,
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

    def handle_post_step(
        self, step_data_input: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> Tuple[dict[str, Any], bool]:
        if not bool(step_data_input.get("enabled")):
            return metadata, True
        post_type = step_data_input.get("type")
        if not post_type:
            app_log(f"❌ Post workflow {workflow_idx} missing 'type'; halting.")
            return metadata, False
        source = (step_data_input.get("source") or "db").lower()
        db_env = step_data_input.get("db_env")
        if not self._confirm_prod_post(workflow_idx):
            return metadata, False
        payload_metadata: dict[str, Any] = {}
        message_payload = None
        if source == "db":
            message_payload, payload_metadata = build_post_message_payload(
                step_data_input,
                post_type,
                self.settings.app.change_warehouse,
                db_env,
            )
        else:
            message_payload = (
                step_data_input.get("message") or self.settings.app.post_message_text
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

    def handle_receive_step(
        self, step_data_input: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> Tuple[dict[str, Any], bool]:
        if not step_data_input:
            return metadata, True

        override_asn = metadata.get("asn_id")
        receive_asn = override_asn if override_asn else step_data_input.get("asn")
        flow_hint = step_data_input.get("flow")
        quantity_override = step_data_input.get("quantity", 0)
        auto_handle = step_data_input.get("auto_handle_deviation", False)
        # Support either legacy "tasks" detour or the newer "ilpns" config
        open_ui_cfg = (
            step_data_input.get("open_ui")
        )

        def _normalize_items() -> list[dict[str, Any]]:
            """Build a list of items to receive from cfg or metadata."""
            cfg_items = step_data_input.get("items")
            if isinstance(cfg_items, Sequence) and not isinstance(cfg_items, (str, bytes)):
                return [item for item in cfg_items if item]

            # Explicit single item on the stage config should take precedence
            explicit_item = step_data_input.get("item")
            if explicit_item:
                return [{"item": explicit_item, "quantity": quantity_override}]

            meta_items = metadata.get("receive_items") or []
            if isinstance(meta_items, Sequence):
                return [item for item in meta_items if item]

            return []

        items_to_receive = _normalize_items()
        if not items_to_receive:
            # Fall back to a single attempt using whatever is in the stage config
            items_to_receive = [{
                "item": step_data_input.get("item"),
                "quantity": quantity_override,
            }]

        for idx, item_cfg in enumerate(items_to_receive, start=1):
            receive_item = (
                item_cfg.get("item")
                or item_cfg.get("ItemName")
                or item_cfg.get("item_name")
            )
            if not receive_item:
                app_log(f"⚠️ Receive step {workflow_idx}: skipping item entry {idx} with no item code.")
                continue

            item_quantity = item_cfg.get("quantity")
            receive_quantity = (
                quantity_override if quantity_override else item_quantity
            )
            if receive_quantity in (None, 0, ""):
                receive_quantity = 1

            receive_result = self.orchestrator.run_with_retry(
                self.step_execution.run_receive,
                f"Receive {receive_item} (Workflow {workflow_idx}, item {idx}/{len(items_to_receive)})",
                asn=receive_asn,
                item=receive_item,
                quantity=receive_quantity,
                flow_hint=flow_hint,
                auto_handle=auto_handle,
                open_ui_cfg=open_ui_cfg,
            )
            if not receive_result.success:
                app_log(f"⏹️ Halting workflow {workflow_idx} due to receive failure")
                return metadata, False
        return metadata, True

    def handle_loading_step(
        self, step_data_input: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> Tuple[dict[str, Any], bool]:
        if not step_data_input:
            return metadata, True
        load_result = self.orchestrator.run_with_retry(
            self.step_execution.run_loading,
            f"Load (Workflow {workflow_idx})",
            shipment=step_data_input.get("shipment"),
            dock_door=step_data_input.get("dock_door"),
            bol=step_data_input.get("bol"),
        )
        if not load_result.success:
            app_log(f"⏹️ Halting workflow {workflow_idx} due to loading failure")
            return metadata, False
        return metadata, True

    def handle_tasks_step(
        self, step_data_input: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> Tuple[dict[str, Any], bool]:
        if not bool(step_data_input.get("enabled", True)):
            return metadata, True
        search_term = step_data_input.get("search_term", "tasks")
        match_text = step_data_input.get("match_text", "Tasks (Configuration)")
        success = self.step_execution.run_open_ui(search_term, match_text)
        if not success:
            app_log(f"❌ Unable to open Tasks UI for workflow {workflow_idx}; halting.")
            return metadata, False
        return metadata, True

    def handle_ilpns_step(
        self, step_data_input: dict[str, Any], metadata: dict[str, Any], workflow_idx: int
    ) -> Tuple[dict[str, Any], bool]:
        if not bool(step_data_input.get("enabled", True)):
            return metadata, True
        search_term = step_data_input.get("search_term", "ilpns")
        match_text = step_data_input.get("match_text", "iLPNs (Distribution)")
        success = self.step_execution.run_open_ui(search_term, match_text)
        if not success:
            app_log(f"❌ Unable to open iLPNs UI for workflow {workflow_idx}; halting.")
            return metadata, False
        return metadata, True


    def run_step(
        self,
        stage_name: str,
        step_data_input: dict[str, Any],
        metadata: dict[str, Any],
        workflow_idx: int,
    ) -> Tuple[dict[str, Any], bool]:
        handler = self.step_handlers.get(stage_name.lower())
        if handler:
            return handler(step_data_input, metadata, workflow_idx)
        app_log(f"ℹ️ No handler for workflow stage '{stage_name}'; skipping.")
        return metadata, True
