"""Coverage for settings helpers and utility functions."""
from types import SimpleNamespace
import sys
from unittest.mock import MagicMock

import pytest

from config import settings as app_settings
from core import logger
from utils import eval_utils, wait_utils


def test_logger_env_parsing_and_verbose_flags(monkeypatch):
    monkeypatch.delenv("APP_VERBOSE_LOGGING", raising=False)
    assert logger._env_bool("APP_VERBOSE_LOGGING") is False
    monkeypatch.setenv("APP_VERBOSE_LOGGING", "YeS")
    assert logger._env_bool("APP_VERBOSE_LOGGING") is True

    logger.set_general_verbose(True)
    logger.set_rf_verbose(False)
    assert logger.is_verbose("general") is True
    assert logger.is_verbose("rf") is False
    assert logger.is_verbose("unknown") is False


def test_get_screen_size_safe_windows(monkeypatch):
    class DummyUser32:
        def __init__(self):
            self.metrics = {0: 800, 1: 600}

        def SetProcessDPIAware(self):
            pass

        def GetSystemMetrics(self, idx):
            return self.metrics[idx]

    dummy_ctypes = SimpleNamespace(windll=SimpleNamespace(user32=DummyUser32()))
    monkeypatch.setattr(app_settings.os, "name", "nt")
    monkeypatch.setattr(app_settings, "ctypes", dummy_ctypes)

    assert app_settings.get_screen_size_safe() == (800, 600)


def test_get_screen_size_safe_fallback(monkeypatch):
    class BrokenTk:
        def __init__(self):
            raise RuntimeError("tk broken")

    monkeypatch.setattr(app_settings.os, "name", "posix")
    monkeypatch.setitem(sys.modules, "tkinter", SimpleNamespace(Tk=BrokenTk))
    logs = []
    monkeypatch.setattr(app_settings, "app_log", lambda msg: logs.append(msg))

    width, height = app_settings.get_screen_size_safe()
    assert (width, height) == (
        app_settings.DEFAULT_SCREEN_WIDTH,
        app_settings.DEFAULT_SCREEN_HEIGHT,
    )
    assert logs


def test_get_scale_factor_windows(monkeypatch):
    class DummyUser32:
        def __init__(self):
            self.released = None

        def SetProcessDPIAware(self):
            pass

        def GetDC(self, handle):
            return "dc"

        def ReleaseDC(self, handle, dc):
            self.released = (handle, dc)

    class DummyGdi32:
        def GetDeviceCaps(self, dc, idx):
            return 192

    dummy_ctypes = SimpleNamespace(
        windll=SimpleNamespace(user32=DummyUser32(), gdi32=DummyGdi32())
    )
    monkeypatch.setattr(app_settings.os, "name", "nt")
    monkeypatch.setattr(app_settings, "ctypes", dummy_ctypes)

    assert app_settings.get_scale_factor() == 2.0


def test_get_scale_factor_fallback(monkeypatch):
    class BrokenTk:
        def __init__(self):
            self.tk = SimpleNamespace(call=lambda *args: (_ for _ in ()).throw(RuntimeError("fail")))

        def withdraw(self):
            pass

        def destroy(self):
            pass

    monkeypatch.setattr(app_settings.os, "name", "posix")
    monkeypatch.setitem(sys.modules, "tkinter", SimpleNamespace(Tk=lambda: BrokenTk()))
    assert app_settings.get_scale_factor() == 1.0


def test_env_flag_parsing(monkeypatch):
    monkeypatch.delenv("FLAG_TEST", raising=False)
    assert app_settings._env_flag("FLAG_TEST", True) is True
    monkeypatch.setenv("FLAG_TEST", "OFF")
    assert app_settings._env_flag("FLAG_TEST", True) is False
    monkeypatch.setenv("FLAG_TEST", "YES")
    assert app_settings._env_flag("FLAG_TEST", False) is True


def test_settings_from_env_handles_credentials_failure(monkeypatch):
    old_app = app_settings.Settings.app
    old_browser = app_settings.Settings.browser
    app_settings.Settings.app = app_settings.AppConfig()
    app_settings.Settings.browser = app_settings.BrowserConfig()

    logs = []
    monkeypatch.setattr(app_settings, "app_log", lambda msg: logs.append(msg))
    monkeypatch.setattr(
        app_settings.DB,
        "get_credentials",
        lambda env: (_ for _ in ()).throw(RuntimeError("creds boom")),
    )
    monkeypatch.setattr(app_settings, "set_general_verbose", lambda flag: None)
    monkeypatch.setattr(app_settings, "set_rf_verbose", lambda flag: None)

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
        assert any("Failed to load App logon credentials" in msg for msg in logs)
    finally:
        app_settings.Settings.app = old_app
        app_settings.Settings.browser = old_browser


def test_safe_page_evaluate_transient(monkeypatch):
    page = MagicMock()
    page.evaluate.side_effect = Exception("target closed unexpectedly")
    with pytest.raises(eval_utils.PageUnavailableError):
        eval_utils.safe_page_evaluate(page, "script")


def test_safe_locator_evaluate_transient(monkeypatch):
    locator = MagicMock()
    locator.evaluate.side_effect = Exception("browser has been closed")
    with pytest.raises(eval_utils.PageUnavailableError):
        eval_utils.safe_locator_evaluate(locator, "script", suppress_log=True)


def test_wait_for_screen_change_detects_change(monkeypatch):
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

    assert wait_utils.WaitUtils.wait_for_screen_change(frame, "old")
    assert frame.page.wait_calls


def test_wait_for_screen_change_times_out(monkeypatch):
    class FakePage:
        def __init__(self):
            self.wait_calls = []

        def wait_for_timeout(self, ms):
            self.wait_calls.append(ms)

    frame = SimpleNamespace(page=FakePage())
    times = iter([0, 50, 120])

    def fake_timer(page, script, description="timer", suppress_log=False):
        try:
            return next(times)
        except StopIteration:
            return 500

    monkeypatch.setattr(wait_utils.HashUtils, "get_frame_snapshot", lambda f: "same")
    monkeypatch.setattr(wait_utils, "safe_page_evaluate", fake_timer)

    assert not wait_utils.WaitUtils.wait_for_screen_change(frame, "same", timeout_ms=200, interval_ms=10)
    assert frame.page.wait_calls


def test_wait_for_screen_change_handles_navigation_error(monkeypatch):
    frame = SimpleNamespace(page=MagicMock())

    def raise_nav_error(_):
        raise RuntimeError("Execution context was destroyed")

    monkeypatch.setattr(wait_utils.HashUtils, "get_frame_snapshot", raise_nav_error)
    monkeypatch.setattr(
        wait_utils,
        "safe_page_evaluate",
        lambda page, script, description="timer", suppress_log=False: 0,
    )

    assert wait_utils.WaitUtils.wait_for_screen_change(frame, "unchanged") is True


def test_wait_for_screen_change_provider_none(monkeypatch):
    monkeypatch.setattr(
        wait_utils,
        "safe_page_evaluate",
        lambda page, script, description="timer", suppress_log=False: 0,
    )
    assert wait_utils.WaitUtils.wait_for_screen_change(lambda: None, "snapshot") is False
