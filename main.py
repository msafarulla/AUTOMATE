"""
Warehouse Automation - Main Entry Point

This script runs configured workflows for warehouse operations.
"""
from typing import Any

from config.operations_config import OperationConfig
from config.settings import Settings
from core.connection_guard import ConnectionResetDetected
from core.logger import app_log
from operations import WorkflowStageExecutor, create_operation_services


def main():
    """Run warehouse automation workflows."""
    settings = Settings.from_env()
    
    with create_operation_services(settings) as wmOps:
        try:
            run_automation(settings, wmOps)
        except ConnectionResetDetected as e:
            app_log(f"❌ Connection lost: {e}")
        except KeyboardInterrupt:
            app_log("\n⚠️ Interrupted by user")
        except Exception as e:
            app_log(f"❌ Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            wmOps.orchestrator.print_summary()


def run_automation(settings: Settings, ops):
    """Execute all configured workflows."""
    app_log("🚀 Starting warehouse automation...")
    
    # Login and setup
    ops.stage_actions.run_login()
    # ops.nav_mgr.close_menu_overlay_after_sign_on()
    if getattr(settings.app, "force_enable_context_menu", False):
        ops.nav_mgr.enable_context_menu()
    ops.stage_actions.run_change_warehouse()

    # Load workflows
    workflows = flatten_workflows(OperationConfig.DEFAULT_WORKFLOWS)
    total = len(workflows)
    
    # Create stage executor
    executor = WorkflowStageExecutor(settings, ops.orchestrator, ops.stage_actions)

    # Run each workflow
    for index, (scenario_name, steps) in enumerate(workflows, 1):
        ops.screenshot_mgr.set_scenario(scenario_name)
        
        app_log("\n" + "=" * 60)
        app_log(f"📦 WORKFLOW {index}/{total}: scenario_{scenario_name}")
        app_log("=" * 60)

        metadata = {}
        for step_name, step_data_input in steps.items():
            ops.screenshot_mgr.set_stage(step_name)
            metadata, should_continue = executor.run_stage(
                step_name, step_data_input, metadata, index
            )
            if not should_continue:
                break

    ops.screenshot_mgr.set_scenario(None)
    app_log("✅ Automation completed!")
    input("Press Enter to exit...")


def flatten_workflows(workflow_map: dict) -> list[tuple[str, dict[str, Any]]]:
    """
    Flatten nested workflow config into list of (name, stages).
    
    Input:  {'inbound': {'receive_happy': {...stages...}}}
    Output: [('inbound.receive_happy', {...stages...})]
    """
    result = []
    for bucket, scenarios in workflow_map.items():
        for scenario, stages in scenarios.items():
            result.append((f"{bucket}.{scenario}", stages))
    return result


if __name__ == "__main__":
    main()
