from config.settings import StepNames
from operations.workflow import WorkflowStageExecutor


class DummySettings:
    def __init__(self):
        self.app = type(
            "App",
            (),
            {
                "step_names": StepNames(),
                "requires_prod_confirmation": False,
                "change_warehouse": "SDC",
            },
        )()


class DummyStepExecution:
    def __init__(self):
        self.calls = []

    def run_receive(self, *args, **kwargs):
        self.calls.append(kwargs)
        return True


class DummyOrchestrator:
    def __init__(self):
        self.calls = []

    def run_with_retry(self, func, operation_name, *args, **kwargs):
        self.calls.append(operation_name)
        result = func(*args, **kwargs)

        class Result:
            def __init__(self, success: bool):
                self.success = success

        return Result(bool(result))


def test_handle_receive_processes_all_metadata_items():
    settings = DummySettings()
    orchestrator = DummyOrchestrator()
    steps = DummyStepExecution()
    executor = WorkflowStageExecutor(settings, orchestrator, steps)

    stage_cfg = {
        "flow": "HAPPY_PATH",
        "auto_handle_deviation": True,
        "quantity": 0,
    }
    metadata = {
        "asn_id": "ASN12345",
        "receive_items": [
            {"item": "ITEM1", "quantity": 3},
            {"item": "ITEM2", "quantity": 4},
        ],
    }

    metadata_out, should_continue = executor.handle_receive_step(stage_cfg, metadata, 1)

    assert should_continue is True
    assert metadata_out is metadata
    assert len(steps.calls) == 2
    assert steps.calls[0]["asn"] == "ASN12345"
    assert steps.calls[0]["item"] == "ITEM1"
    assert steps.calls[0]["quantity"] == 3
    assert steps.calls[1]["item"] == "ITEM2"
    assert steps.calls[1]["quantity"] == 4


def test_handle_receive_respects_stage_items_and_quantity_override():
    settings = DummySettings()
    orchestrator = DummyOrchestrator()
    steps = DummyStepExecution()
    executor = WorkflowStageExecutor(settings, orchestrator, steps)

    stage_cfg = {
        "asn": "ASN999",
        "items": [
            {"item": "ITEM1", "quantity": 1},
            {"item": "ITEM2"},
        ],
        "quantity": 7,
    }

    metadata = {}

    _, should_continue = executor.handle_receive_step(stage_cfg, metadata, 2)

    assert should_continue is True
    assert [call["item"] for call in steps.calls] == ["ITEM1", "ITEM2"]
    assert all(call["quantity"] == 7 for call in steps.calls)
    assert all(call["asn"] == "ASN999" for call in steps.calls)
