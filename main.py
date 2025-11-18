from typing import Any

from config.operations_config import OperationConfig
from config.settings import Settings
from core.connection_guard import ConnectionResetDetected
from core.logger import app_log
from operations import WorkflowStageExecutor, create_operation_services


def main():
    settings = Settings.from_env()
    with create_operation_services(settings) as ops:
        stage_executor = WorkflowStageExecutor(
            settings,
            ops.orchestrator,
            ops.stage_actions,
        )

        try:
            app_log("🚀 Starting warehouse automation...")
        ops.stage_actions.run_login()
        ops.nav_mgr.close_menu_overlay_after_sign_on()
        ops.stage_actions.run_change_warehouse()

            workflow_map = OperationConfig.DEFAULT_WORKFLOWS
            workflow_items: list[tuple[str, dict[str, Any]]] = []
            for bucket_name, bucket in workflow_map.items():
                for scenario_name, workflow in bucket.items():
                    workflow_items.append((f"{bucket_name}.{scenario_name}", workflow))
            total_workflows = len(workflow_items)

            for index, (scenario_label, workflow) in enumerate(workflow_items, 1):
                ops.screenshot_mgr.set_scenario(scenario_label)
                app_log("\n" + "=" * 60)
                app_log(f"📦 WORKFLOW {index}/{total_workflows} ({scenario_label})")
                app_log("=" * 60)

                workflow_metadata: dict[str, Any] = {}
                for stage_name, stage_cfg in workflow.items():
                    ops.screenshot_mgr.set_stage(stage_name)
                    stage_cfg = stage_cfg or {}
                    workflow_metadata, continue_run = stage_executor.run_stage(
                        stage_name, stage_cfg, workflow_metadata, index
                    )
                    if not continue_run:
                        break

            ops.orchestrator.print_summary()
            app_log("✅ Automation completed!")
            input("Press Enter to exit...")

        except ConnectionResetDetected as exc:
            app_log(f"❌ Connection lost: {exc}")
            ops.orchestrator.print_summary()
        except KeyboardInterrupt:
            app_log("\n⚠️ Interrupted by user")
            ops.orchestrator.print_summary()
        except Exception as exc:
            app_log(f"❌ Fatal error in main flow: {exc}")
            import traceback

            traceback.print_exc()
            ops.orchestrator.print_summary()
        finally:
            ops.screenshot_mgr.set_scenario(None)


if __name__ == "__main__":
    main()
