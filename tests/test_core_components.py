"""Additional coverage for core components and orchestration helpers."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.orchestrator import AutomationOrchestrator, OperationResult
from core.page_manager import PageManager
from core.screenshot import ScreenshotManager, PlaywrightTimeoutError
from operations.base_operation import BaseOperation
from operations.runner import OperationRunner
from operations.workflow import WorkflowStageExecutor
from utils.eval_utils import PageUnavailableError
from config.settings import StepNames


class DummyOp(BaseOperation):
    """Concrete subclass for testing BaseOperation behavior."""

    def execute(self, *args, **kwargs):
        return "executed"


def test_base_operation_handle_error_screen():
    page = MagicMock()
    page.mouse.move = MagicMock()
    rf_menu = MagicMock()
    rf_menu.check_for_response.return_value = (True, "error detected")

    op = DummyOp(page, MagicMock(), MagicMock(), rf_menu)
    has_error, msg = op.handle_error_screen("iframe")

    assert has_error is True
    assert msg == "error detected"
    rf_menu.accept_proceed.assert_called_once_with("iframe")
    page.mouse.move.assert_called_once()


def test_base_operation_handle_error_screen_no_message():
    page = MagicMock()
    rf_menu = MagicMock()
    rf_menu.check_for_response.return_value = (False, None)

    op = DummyOp(page, MagicMock(), MagicMock(), rf_menu)
    has_error, msg = op.handle_error_screen("iframe")

    assert has_error is False
    assert msg is None
    rf_menu.accept_proceed.assert_not_called()


class _FakeFrame:
    def __init__(self, name=None, url=None, raise_on_name=False, detached=False):
        self._name = name
        self._url = url
        self._raise_on_name = raise_on_name
        self._detached = detached

    def is_detached(self):
        return self._detached

    @property
    def name(self):
        if self._raise_on_name:
            raise RuntimeError("name failure")
        return self._name

    @property
    def url(self):
        if self._raise_on_name:
            raise RuntimeError("url failure")
        return self._url


class _FakePage:
    def __init__(self, frames, main_frame):
        self.frames = frames
        self.main_frame = main_frame

    def add_init_script(self, *_args, **_kwargs):
        pass


def test_page_manager_skips_error_frames_and_returns_rfmenu():
    """Exception during frame inspection should be skipped."""
    good = _FakeFrame(name="uxiframe_rf", url="http://test/RFMenu")
    bad = _FakeFrame(raise_on_name=True)
    page = _FakePage([good, bad], main_frame=MagicMock())

    mgr = PageManager(page)
    result = mgr.get_rf_iframe()

    assert result is good


def test_page_manager_falls_back_to_main_frame(monkeypatch):
    """When no usable frames exist, main_frame is returned."""
    bad = _FakeFrame(raise_on_name=True)
    page = _FakePage([bad], main_frame=MagicMock())

    mgr = PageManager(page)
    result = mgr.get_rf_iframe()

    assert result is page.main_frame


@patch("core.screenshot.Path")
def test_capture_handles_overlay_cleanup_errors(mock_path_class):
    """Ensure overlay/timestamp cleanup errors are swallowed."""
    mock_path = MagicMock()
    mock_path_class.return_value = mock_path
    mock_filename = MagicMock()
    mock_path.__truediv__.return_value = mock_filename

    mgr = ScreenshotManager()
    mgr._add_overlay = MagicMock()
    mgr._add_timestamp = MagicMock()
    mgr._remove_overlay = MagicMock(side_effect=PageUnavailableError("closed"))
    mgr._remove_timestamp = MagicMock(side_effect=PageUnavailableError("closed"))

    mock_page = MagicMock()

    result = mgr.capture(mock_page, "label", overlay_text="with_overlay")

    assert result == mock_filename
    assert mgr.sequence == 1


@patch("core.screenshot.Path")
def test_capture_timeout_retry_with_quality_and_page_unavailable(mock_path_class):
    """Retry path should include quality flag and handle retry failures."""
    mock_path = MagicMock()
    mock_path_class.return_value = mock_path

    mgr = ScreenshotManager(image_format="jpeg", image_quality=75)
    mgr._add_overlay = MagicMock()
    mgr._add_timestamp = MagicMock()
    mgr._remove_timestamp = MagicMock(side_effect=PageUnavailableError("closed"))

    mock_page = MagicMock()
    mock_page.screenshot.side_effect = [
        PlaywrightTimeoutError("Timeout"),  # initial attempt
        PageUnavailableError("closed"),     # retry attempt
    ]

    result = mgr.capture(mock_page, "label", overlay_text=None)
    assert result is None
    assert mgr.sequence == 0
    # Quality flag should be included on retry call
    retry_kwargs = mock_page.screenshot.call_args_list[1].kwargs
    assert retry_kwargs.get("quality") == 75


@patch("core.screenshot.Path")
def test_capture_rf_window_with_overlay_and_cleanup_errors(mock_path_class):
    """Cover overlay and cleanup branches in RF capture."""
    mock_path = MagicMock()
    mock_path_class.return_value = mock_path
    mock_filename = MagicMock()
    mock_path.__truediv__.return_value = mock_filename

    mgr = ScreenshotManager()
    mgr._get_element_rect = MagicMock(return_value={"top": 0, "right": 0})
    mgr._add_overlay_to_target = MagicMock()
    mgr._add_timestamp = MagicMock(side_effect=PageUnavailableError("nope"))
    mgr._remove_overlay_from_target = MagicMock(side_effect=PageUnavailableError("gone"))
    mgr._remove_timestamp = MagicMock()

    mock_page = MagicMock()
    mock_target = MagicMock()
    mock_target.wait_for = MagicMock()
    mock_target.screenshot = MagicMock()
    mock_locator = MagicMock(first=mock_target)
    mock_page.locator.return_value = mock_locator

    result = mgr.capture_rf_window(mock_page, "rf_label", overlay_text="Overlay")

    assert result == mock_filename
    assert mgr.sequence == 1
    mgr._add_overlay_to_target.assert_called_once()
    mgr._remove_overlay_from_target.assert_called_once()


@patch("core.screenshot.Path")
def test_capture_rf_window_handles_page_unavailable(mock_path_class):
    """PageUnavailableError during RF capture should return None."""
    mock_path = MagicMock()
    mock_path_class.return_value = mock_path

    mgr = ScreenshotManager()
    mock_page = MagicMock()
    mock_page.locator.side_effect = PageUnavailableError("closed")

    result = mgr.capture_rf_window(mock_page, "rf_label")
    assert result is None
    assert mgr.sequence == 0


@patch("core.screenshot.safe_page_evaluate")
def test_overlay_helpers_execute_scripts(mock_safe_eval):
    """Directly exercise overlay helper methods."""
    mock_safe_eval.return_value = None
    mock_page = MagicMock()
    mock_page.wait_for_timeout = MagicMock()

    mgr = ScreenshotManager()
    mgr._add_overlay(mock_page, "text", top_offset=12.5)
    mgr._remove_overlay(mock_page)

    assert mock_safe_eval.call_count == 2
    mock_page.wait_for_timeout.assert_called_once()


def test_overlay_target_helpers():
    """Ensure target overlay helpers invoke evaluate."""
    mgr = ScreenshotManager()
    target = MagicMock()

    mgr._add_overlay_to_target(target, "hello", top_offset=5)
    mgr._remove_overlay_from_target(target)

    assert target.evaluate.call_count == 2


class DummySettings:
    def __init__(self):
        self.app = SimpleNamespace(
            step_names=StepNames(),
            requires_prod_confirmation=False,
            change_warehouse="SDC",
            post_message_text="DEFAULT",
            rf_verbose_logging=False,
            auto_click_info_icon=False,
            verify_tran_id_marker=False,
        )


class DummyStepExecution:
    def __init__(self, succeed=True):
        self.calls = []
        self.succeed = succeed

    def run_post_message(self, payload=None):
        self.calls.append(payload)
        return self.succeed

    def run_receive(self, *args, **kwargs):
        self.calls.append(kwargs)
        return self.succeed

    def run_loading(self, *args, **kwargs):
        self.calls.append(kwargs)
        return self.succeed

    def run_open_ui(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.succeed


class DummyOrchestrator:
    def __init__(self, success=True):
        self.success = success
        self.calls = []

    def run_with_retry(self, func, operation_name, *args, **kwargs):
        self.calls.append((operation_name, kwargs))

        class Result:
            def __init__(self, success):
                self.success = success

        return Result(self.success and func(*args, **kwargs))


def test_workflow_post_step_variants(monkeypatch):
    settings = DummySettings()
    orchestrator = DummyOrchestrator()
    steps = DummyStepExecution()
    executor = WorkflowStageExecutor(settings, orchestrator, steps)

    metadata = {"existing": True}

    # Disabled stage
    meta_out, cont = executor.handle_post_step({"enabled": False}, metadata, 0)
    assert cont is True and meta_out is metadata

    # Missing type
    _, cont = executor.handle_post_step({"enabled": True}, metadata, 1)
    assert cont is False

    # DB payload missing
    monkeypatch.setattr(
        "operations.workflow.build_post_message_payload",
        lambda *args, **kwargs: (None, {}),
    )
    _, cont = executor.handle_post_step({"type": "asn", "enabled": True}, metadata, 2)
    assert cont is False

    # Direct message success
    meta_out, cont = executor.handle_post_step(
        {"type": "asn", "source": "text", "message": "hi", "enabled": True},
        metadata,
        3,
    )
    assert cont is True
    assert meta_out is metadata
    assert steps.calls[-1] == "hi"


def test_workflow_loading_and_tasks(monkeypatch):
    settings = DummySettings()
    orchestrator = DummyOrchestrator(success=False)
    steps = DummyStepExecution()
    executor = WorkflowStageExecutor(settings, orchestrator, steps)

    # Loading failure should halt
    _, cont = executor.handle_loading_step({"shipment": "S1"}, {}, 1)
    assert cont is False

    # Disabled tasks step
    _, cont = executor.handle_tasks_step({"enabled": False}, {}, 2)
    assert cont is True

    # Failed tasks step
    steps_fail = DummyStepExecution(succeed=False)
    executor_fail = WorkflowStageExecutor(settings, orchestrator, steps_fail)
    _, cont = executor_fail.handle_tasks_step({}, {}, 3)
    assert cont is False

    # iLPNs success with custom args
    steps_success = DummyStepExecution(succeed=True)
    executor_success = WorkflowStageExecutor(settings, orchestrator, steps_success)
    _, cont = executor_success.handle_ilpns_step(
        {"search_term": "ilpns", "match_text": "iLPNs"}, {}, 4
    )
    assert cont is True
    assert steps_success.calls[-1][0][0] == "ilpns"


def test_workflow_run_step_unknown():
    settings = DummySettings()
    executor = WorkflowStageExecutor(settings, DummyOrchestrator(), DummyStepExecution())
    meta, cont = executor.run_step("unknown_stage", {}, {}, 1)
    assert cont is True
    assert meta == {}


def test_automation_orchestrator_runs_and_retries():
    orch = AutomationOrchestrator(settings=MagicMock(), max_retries=2)

    success = orch.run_with_retry(lambda: True, "SuccessOp")
    assert success.success is True
    assert success.retry_count == 0

    failure = orch.run_with_retry(lambda: False, "FailOp")
    assert failure.success is False
    assert failure.retry_count == 2
    assert failure.error == "Operation returned False"

    counter = {"calls": 0}

    def flaky():
        counter["calls"] += 1
        if counter["calls"] == 1:
            raise ValueError("boom")
        return True

    retry = orch.run_with_retry(flaky, "FlakyOp")
    assert retry.success is True
    assert retry.retry_count == 1
    assert len(orch.results) == 3


def test_automation_orchestrator_summary(monkeypatch):
    orch = AutomationOrchestrator(settings=MagicMock())
    orch.results = [
        OperationResult(True, "Op1"),
        OperationResult(False, "Op2", error="bad"),
    ]
    logs = []
    monkeypatch.setattr("core.orchestrator.app_log", lambda msg: logs.append(msg))

    orch.print_summary()
    assert any("Op2" in line for line in logs)


class DummyGuard:
    def __init__(self):
        self.calls = []

    def guard(self, func, *args, **kwargs):
        self.calls.append((func.__name__, args, kwargs))
        return func(*args, **kwargs)


class DummySettingsApp:
    def __init__(self):
        self.change_warehouse = "WH1"
        self.post_message_text = "DEFAULT"
        self.rf_verbose_logging = False
        self.auto_click_info_icon = False
        self.verify_tran_id_marker = False


class DummySettingsRunner:
    def __init__(self):
        self.app = DummySettingsApp()


def _build_runner(monkeypatch, settings=None):
    settings = settings or DummySettingsRunner()
    page = MagicMock()
    page_mgr = MagicMock()
    screenshot_mgr = MagicMock()
    auth_mgr = MagicMock()
    nav_mgr = MagicMock()
    detour_page = MagicMock()
    post_message_mgr = MagicMock()
    rf_menu = MagicMock()
    conn_guard = DummyGuard()

    # Patch operations to avoid real Playwright usage
    receive_instances = {}
    loading_instances = {}

    class DummyReceiveOperation:
        def __init__(self, *args, **kwargs):
            receive_instances["instance"] = self

        def execute(self, *args, **kwargs):
            receive_instances["args"] = (args, kwargs)
            return True

    class DummyLoadingOperation:
        def __init__(self, *args, **kwargs):
            loading_instances["instance"] = self

        def execute(self, *args, **kwargs):
            loading_instances["args"] = (args, kwargs)
            return True

    monkeypatch.setattr("operations.runner.ReceiveOperation", DummyReceiveOperation)
    monkeypatch.setattr("operations.runner.LoadingOperation", DummyLoadingOperation)

    runner = OperationRunner(
        settings,
        page,
        page_mgr,
        screenshot_mgr,
        auth_mgr,
        nav_mgr,
        detour_page,
        post_message_mgr,
        rf_menu,
        conn_guard,
    )
    return runner, {
        "page": page,
        "page_mgr": page_mgr,
        "screenshot_mgr": screenshot_mgr,
        "auth_mgr": auth_mgr,
        "nav_mgr": nav_mgr,
        "detour_page": detour_page,
        "post_message_mgr": post_message_mgr,
        "rf_menu": rf_menu,
        "conn_guard": conn_guard,
        "receive_instances": receive_instances,
        "loading_instances": loading_instances,
    }


def test_operation_runner_uses_guard(monkeypatch):
    runner, deps = _build_runner(monkeypatch)
    runner.run_login()
    runner.run_change_warehouse()

    assert deps["auth_mgr"].login.called
    assert ("_run_login",) in [(c[0],) for c in deps["conn_guard"].calls]
    assert deps["nav_mgr"].change_warehouse.called


def test_operation_runner_post_message_paths(monkeypatch):
    settings = DummySettingsRunner()
    settings.app.post_message_text = ""
    runner, deps = _build_runner(monkeypatch, settings=settings)
    deps["post_message_mgr"].send_message.return_value = (True, {"summary": "ok"})

    assert runner.run_post_message() is False
    deps["post_message_mgr"].send_message.assert_not_called()

    settings.app.post_message_text = "PAYLOAD"
    deps["post_message_mgr"].send_message.return_value = (
        True,
        {"summary": "ok", "payload": "<xml/>"},
    )
    assert runner.run_post_message() is True
    deps["post_message_mgr"].send_message.assert_called_once()
    deps["screenshot_mgr"].capture_rf_window.assert_called_once()


def test_operation_runner_receive_and_loading(monkeypatch):
    runner, deps = _build_runner(monkeypatch)

    assert runner.run_receive("ASN1", "ITEM1", quantity=2)
    assert deps["nav_mgr"].open_menu_item.called
    assert deps["receive_instances"]["args"][0][0] == "ASN1"

    assert runner.run_loading("SHIP1", "DOOR1", "BOL1")
    assert deps["loading_instances"]["args"][0][0] == "SHIP1"


def test_operation_runner_open_ui(monkeypatch):
    runner, deps = _build_runner(monkeypatch)
    deps["nav_mgr"].open_tasks_ui.return_value = False

    assert runner.run_open_ui("tasks", "Tasks (Configuration)") is False
    deps["nav_mgr"].open_tasks_ui.assert_called_once()
