"""Additional coverage for utility and configuration helpers."""
from types import SimpleNamespace
import sys
from unittest.mock import MagicMock

import pytest

from core import logger
from config import settings as app_settings
from utils import eval_utils, wait_utils


def test_logger_env_parsing_and_verbose_flags(monkeypatch):
    """Ensure env parsing and channel verbosity toggles behave."""
    monkeypatch.delenv("APP_VERBOSE_LOGGING", raising=False)
    assert logger._env_bool("APP_VERBOSE_LOGGING") is False

    monkeypatch.setenv("APP_VERBOSE_LOGGING", "YeS")
    assert logger._env_bool("APP_VERBOSE_LOGGING") is True

    logger.set_general_verbose(True)
    logger.set_rf_verbose(False)
    assert logger.is_verbose("general") is True
    assert logger.is_verbose("rf") is False
    assert logger.is_verbose("unknown-channel") is False


def test_get_screen_size_safe_windows(monkeypatch):
    """Cover Windows branch using a stubbed ctypes module."""
    class DummyUser32:
        def __init__(self):
            self.calls = []

        def SetProcessDPIAware(self):
            self.calls.append("dpi")

        def GetSystemMetrics(self, idx):
            return {0: 800, 1: 600}[idx]

    dummy_user32 = DummyUser32()
    dummy_ctypes = SimpleNamespace(windll=SimpleNamespace(user32=dummy_user32))

    monkeypatch.setattr(app_settings.os, "name", "nt")
    monkeypatch.setattr(app_settings, "ctypes", dummy_ctypes)

    width, height = app_settings.get_screen_size_safe()
    assert (width, height) == (800, 600)


def test_get_screen_size_and_scale_with_tk(monkeypatch):
    """Use a fake tkinter module to exercise non-Windows branches."""
    class DummyRoot:
        def __init__(self):
            self.tk = SimpleNamespace(call=lambda *args: 1.5)

        def withdraw(self):
            pass

        def winfo_screenwidth(self):
            return 1600

        def winfo_screenheight(self):
            return 900

        def destroy(self):
            pass

    class DummyTkModule:
        def __init__(self, root):
            self._root = root

        def Tk(self):
            return self._root

    dummy_root = DummyRoot()
    monkeypatch.setattr(app_settings.os, "name", "posix")
    monkeypatch.setitem(sys.modules, "tkinter", DummyTkModule(dummy_root))

    width, height = app_settings.get_screen_size_safe()
    assert (width, height) == (1600, 900)

    scale = app_settings.get_scale_factor()
    assert scale == 1.5


def test_get_scale_factor_windows(monkeypatch):
    """Verify DPI-based scale factor detection on Windows branch."""
    class DummyUser32:
        def __init__(self):
            self.dcs = []

        def SetProcessDPIAware(self):
            pass

        def GetDC(self, handle):
            self.dcs.append(handle)
            return "dc-handle"

        def ReleaseDC(self, handle, dc):
            self.released = (handle, dc)

    class DummyGdi32:
        def GetDeviceCaps(self, dc, idx):
            assert dc == "dc-handle"
            return 192  # 2x DPI

    dummy_ctypes = SimpleNamespace(
        windll=SimpleNamespace(user32=DummyUser32(), gdi32=DummyGdi32())
    )
    monkeypatch.setattr(app_settings.os, "name", "nt")
    monkeypatch.setattr(app_settings, "ctypes", dummy_ctypes)

    assert app_settings.get_scale_factor() == 2.0


def test_safe_page_evaluate_transient(monkeypatch):
    """Transient Playwright errors should raise PageUnavailableError."""
    page = MagicMock()
    page.evaluate.side_effect = Exception("Target closed unexpectedly")

    with pytest.raises(eval_utils.PageUnavailableError):
        eval_utils.safe_page_evaluate(page, "script")


def test_safe_page_evaluate_with_arg(monkeypatch):
    """Ensure argument-bearing evaluations pass through correctly."""
    page = MagicMock()
    page.evaluate.side_effect = lambda script, arg=None: arg or script

    result = eval_utils.safe_page_evaluate(page, "script", arg={"value": 1})
    assert result == {"value": 1}


def test_safe_locator_evaluate_transient_suppressed(monkeypatch):
    """Locator transient errors should also map to PageUnavailableError."""
    locator = MagicMock()
    locator.evaluate.side_effect = Exception("browser has been closed")

    with pytest.raises(eval_utils.PageUnavailableError):
        eval_utils.safe_locator_evaluate(locator, "script", suppress_log=True)


def test_wait_for_screen_change_detects_change(monkeypatch):
    """Stop early when a new snapshot appears."""
    class FakePage:
        def __init__(self):
            self.wait_calls = []

        def wait_for_timeout(self, ms):
            self.wait_calls.append(ms)

    frame = SimpleNamespace(page=FakePage())

    monkeypatch.setattr(wait_utils.HashUtils, "get_frame_snapshot", lambda f: "new")
    monkeypatch.setattr(
        wait_utils,
        "safe_page_evaluate",
        lambda page, script, description="timer", suppress_log=False: 0,
    )

    changed = wait_utils.WaitUtils.wait_for_screen_change(frame, "old", timeout_ms=1000)
    assert changed is True
    assert frame.page.wait_calls  # ensures loop executed at least once


def test_wait_for_screen_change_times_out(monkeypatch):
    """Timeout branch should fire when content is unchanged."""
    class FakePage:
        def __init__(self):
            self.wait_calls = []

        def wait_for_timeout(self, ms):
            self.wait_calls.append(ms)

    frame = SimpleNamespace(page=FakePage())

    times = iter([0, 100, 250])

    def fake_timer(page, script, description="timer", suppress_log=False):
        try:
            return next(times)
        except StopIteration:
            return 500

    monkeypatch.setattr(wait_utils.HashUtils, "get_frame_snapshot", lambda f: "same")
    monkeypatch.setattr(wait_utils, "safe_page_evaluate", fake_timer)

    changed = wait_utils.WaitUtils.wait_for_screen_change(
        frame, "same", timeout_ms=200, interval_ms=10
    )
    assert changed is False
    assert len(frame.page.wait_calls) >= 2


def test_wait_for_screen_change_handles_navigation_error(monkeypatch):
    """Navigation errors should be treated as a change."""
    frame = SimpleNamespace(page=MagicMock())

    def raise_nav_error(_):
        raise RuntimeError("Execution context was destroyed")

    monkeypatch.setattr(wait_utils.HashUtils, "get_frame_snapshot", raise_nav_error)
    monkeypatch.setattr(
        wait_utils, "safe_page_evaluate", lambda page, script, description="timer", suppress_log=False: 0
    )

    changed = wait_utils.WaitUtils.wait_for_screen_change(frame, "unchanged")
    assert changed is True


def test_wait_for_screen_change_provider_none(monkeypatch):
    """None-returning frame provider should be handled gracefully."""
    monkeypatch.setattr(
        wait_utils, "safe_page_evaluate", lambda page, script, description="timer", suppress_log=False: 0
    )
    changed = wait_utils.WaitUtils.wait_for_screen_change(lambda: None, "snapshot")
    assert changed is False


def test_get_screen_size_safe_fallback(monkeypatch):
    """If Tk fails, defaults should be used."""
    class RaisingTk:
        def __init__(self):
            raise RuntimeError("tk broken")

    class RaisingTkModule:
        Tk = RaisingTk

    monkeypatch.setattr(app_settings.os, "name", "posix")
    monkeypatch.setitem(sys.modules, "tkinter", RaisingTkModule())
    logs = []
    monkeypatch.setattr(app_settings, "app_log", lambda msg: logs.append(msg))

    width, height = app_settings.get_screen_size_safe()
    assert (width, height) == (
        app_settings.DEFAULT_SCREEN_WIDTH,
        app_settings.DEFAULT_SCREEN_HEIGHT,
    )
    assert logs  # warning logged


def test_get_scale_factor_fallback(monkeypatch):
    """Scale factor errors should fall back to 1.0."""
    class BrokenTk:
        def __init__(self):
            self.tk = SimpleNamespace(call=lambda *args: (_ for _ in ()).throw(RuntimeError("fail")))

        def withdraw(self):
            pass

        def destroy(self):
            pass

    class BrokenTkModule:
        def Tk(self):
            return BrokenTk()

    monkeypatch.setitem(sys.modules, "tkinter", BrokenTkModule())
    monkeypatch.setattr(app_settings.os, "name", "posix")
    assert app_settings.get_scale_factor() == 1.0


def test_env_flag_parsing_defaults(monkeypatch):
    """_env_flag should respect defaults and common values."""
    monkeypatch.delenv("FLAG1", raising=False)
    assert app_settings._env_flag("FLAG1", True) is True
    monkeypatch.setenv("FLAG1", "off")
    assert app_settings._env_flag("FLAG1", True) is False
    monkeypatch.setenv("FLAG1", "YES")
    assert app_settings._env_flag("FLAG1", False) is True


def test_settings_from_env_handles_credentials_failure(monkeypatch):
    """from_env should survive credential errors and set flags."""
    old_app = app_settings.Settings.app
    old_browser = app_settings.Settings.browser
    app_settings.Settings.app = app_settings.AppConfig()
    app_settings.Settings.browser = app_settings.BrowserConfig()

    logs = []
    monkeypatch.setattr(app_settings, "app_log", lambda msg: logs.append(msg))
    monkeypatch.setattr(
        app_settings.DB, "get_credentials", lambda env: (_ for _ in ()).throw(RuntimeError("creds boom"))
    )
    general_calls = []
    rf_calls = []
    monkeypatch.setattr(app_settings, "set_general_verbose", lambda flag: general_calls.append(flag))
    monkeypatch.setattr(app_settings, "set_rf_verbose", lambda flag: rf_calls.append(flag))

    monkeypatch.setenv("DEFAULT_WAREHOUSE", "WH2")
    monkeypatch.setenv("POST_MESSAGE_TEXT", "HELLO")
    monkeypatch.setenv("APP_VERBOSE_LOGGING", "0")
    monkeypatch.setenv("RF_VERBOSE_LOGGING", "1")
    monkeypatch.setenv("RF_AUTO_ACCEPT_MESSAGES", "off")
    monkeypatch.setenv("RF_AUTO_CLICK_INFO_ICON", "yes")
    monkeypatch.setenv("RF_VERIFY_TRAN_ID_MARKER", "true")
    monkeypatch.setenv("AUTO_CLOSE_POST_LOGIN_WINDOWS", "on")
    monkeypatch.setenv("APP_CREDENTIALS_ENV", "prod")
    monkeypatch.setenv("APP_SERVER", "prd-host")
    monkeypatch.setenv("APP_SERVER_USER", "svc_user")
    monkeypatch.setenv("APP_SERVER_PASS", "svc_pass")

    try:
        app_settings.Settings.from_env()
        app = app_settings.Settings.app
        assert app.change_warehouse == "WH2"
        assert app.post_message_text == "HELLO"
        assert app.auto_accept_rf_messages is False
        assert app.auto_click_info_icon is True
        assert app.verify_tran_id_marker is True
        assert app.auto_close_post_login_windows is True
        assert app.credentials_env == "prod"
        assert app.app_server == "prd-host"
        assert app.app_server_user == "svc_user"
        assert app.app_server_pass == "svc_pass"
        assert app.requires_prod_confirmation is True
        assert general_calls == [False]
        assert rf_calls == [True]
        assert any("Failed to load App logon credentials" in msg for msg in logs)
    finally:
        app_settings.Settings.app = old_app
        app_settings.Settings.browser = old_browser
