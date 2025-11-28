"""
Warehouse Automation - Main Entry Point

This script runs configured workflows for warehouse operations.
"""
from typing import Any, cast

from config.operations_config import OperationConfig
from config.settings import Settings
from core.connection_guard import ConnectionResetDetected
from core.logger import app_log
from operations import create_operation_services

# Import new workflow system (optional - for gradual migration)
create_default_workflows = None  # type: ignore
flatten_new_workflows = None  # type: ignore
Workflow = None  # type: ignore
try:
    from config.workflow_config import (
        Workflow,
        create_default_workflows,
        flatten_workflows as flatten_new_workflows,
    )
    NEW_WORKFLOW_SYSTEM = True
except ImportError:
    NEW_WORKFLOW_SYSTEM = False


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


def run_automation(settings: Settings, wmOps):
    """Execute all configured workflows."""

    # Step 1: Login and setup
    wmOps.step_execution.run_login()           # Opens browser, fills credentials
    wmOps.step_execution.run_change_warehouse() # Selects the right warehouse

    # Step 2: Load workflow configurations
    workflows = load_workflows()  # Returns list of (name, steps) tuples

    # Step 3: Run each workflow
    for index, (scenario_name, steps) in enumerate(workflows, 1):
        wmOps.screenshot_mgr.set_scenario(scenario_name)  # Organize screenshots

        metadata: dict[str, Any] = {}
        for step_name, step_data_input in steps.items():
            wmOps.screenshot_mgr.set_stage(step_name)
            metadata, should_continue = wmOps.executor.run_step(
                step_name, step_data_input, metadata, index
            )
            if not should_continue:
                break  # Stop this workflow if step failed

    wmOps.screenshot_mgr.set_scenario(None)
    app_log("✅ Automation completed!")
    input("Press Enter to exit...")


def load_workflows() -> list[tuple[str, dict[str, Any]]]:
    """
    Load workflows from configuration.
    
    Supports both:
    - New WorkflowBuilder system (if available)
    - Legacy nested dict format (fallback)
    """
    # Try new system first
    if NEW_WORKFLOW_SYSTEM and callable(create_default_workflows) and callable(flatten_new_workflows):
        try:
            workflows = cast(list[Any], create_default_workflows())
            if workflows:
                app_log(f"📋 Loaded {len(workflows)} workflows (new format)")
                return cast(list[tuple[str, dict[str, Any]]], flatten_new_workflows(workflows))
        except Exception as e:
            app_log(f"⚠️ Failed to load new workflows: {e}")

    # Fall back to legacy format
    app_log("📋 Using legacy workflow configuration")
    return flatten_legacy_workflows(OperationConfig.DEFAULT_WORKFLOWS)


def flatten_legacy_workflows(workflow_map: dict) -> list[tuple[str, dict[str, Any]]]:
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
