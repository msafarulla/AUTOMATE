"""Tests for core.detour helpers."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.detour import ensure_detour_page_ready, run_open_ui_detours


def test_ensure_detour_page_ready_short_circuit():
    """Returns True when detour page already has a valid URL."""
    detour_page = SimpleNamespace(url="http://already-set")
    assert ensure_detour_page_ready(detour_page) is True


def test_ensure_detour_page_ready_with_main_page(monkeypatch):
    """Should navigate using main page URL and change warehouse."""
    created_nav = []

    class DummyNav:
        def __init__(self, page, screenshot_mgr):
            created_nav.append(self)
            self.page = page
            self.screenshot_mgr = screenshot_mgr
            self.changed = False
            self.closed = False

        def change_warehouse(self, whse, onDemand=True):
            self.changed = (whse, onDemand)

    monkeypatch.setattr("core.detour.NavigationManager", DummyNav)

    detour_page = MagicMock()
    detour_page.url = "about:blank"
    detour_page.goto = MagicMock()
    detour_page.wait_for_timeout = MagicMock()

    main_page = SimpleNamespace(url="http://main-app")
    settings = SimpleNamespace(app=SimpleNamespace(app_server="http://ignored", change_warehouse="WH1"))

    result = ensure_detour_page_ready(detour_page, main_page=main_page, settings=settings, screenshot_mgr="ss")

    assert result is True
    detour_page.goto.assert_called_once_with("http://main-app", wait_until="networkidle", timeout=20000)
    assert created_nav and created_nav[0].changed == ("WH1", False)


def test_ensure_detour_page_ready_uses_app_server(monkeypatch):
    """Fallback to app_server when main page URL is unusable."""
    monkeypatch.setattr("core.detour.NavigationManager", lambda page, ss: SimpleNamespace(change_warehouse=lambda *a, **k: None))
    detour_page = MagicMock()
    detour_page.url = "about:blank"
    detour_page.goto = MagicMock()
    detour_page.wait_for_timeout = MagicMock()
    main_page = SimpleNamespace(url="about:blank")
    settings = SimpleNamespace(app=SimpleNamespace(app_server="http://server", change_warehouse=None))

    assert ensure_detour_page_ready(detour_page, main_page=main_page, settings=settings)
    detour_page.goto.assert_called_once_with("http://server", wait_until="networkidle", timeout=20000)


def test_ensure_detour_page_ready_returns_false_on_errors(monkeypatch):
    """Errors or missing source URLs should return False."""
    detour_page = MagicMock()
    type(detour_page).url = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    assert ensure_detour_page_ready(detour_page) is False

    detour_page = MagicMock()
    detour_page.url = "about:blank"
    detour_page.goto.side_effect = RuntimeError("fail")
    settings = SimpleNamespace(app=SimpleNamespace(app_server="about:blank", change_warehouse=None))
    assert ensure_detour_page_ready(detour_page, settings=settings) is False


def test_run_open_ui_detours_success_with_detour_page(monkeypatch):
    """Covers detour navigation, closing windows, screenshot tagging, and fill_ilpn callback."""
    ensure_calls = []
    monkeypatch.setattr("core.detour.ensure_detour_page_ready", lambda *a, **k: ensure_calls.append(a) or True)

    rf_logs = []
    monkeypatch.setattr("core.detour.rf_log", lambda msg: rf_logs.append(msg))
    app_logs = []
    monkeypatch.setattr("core.detour.app_log", lambda msg: app_logs.append(msg))

    class DummyNav:
        def __init__(self, page, screenshot_mgr):
            self.page = page
            self.closed = 0
            self.maximized = 0
            self.open_calls = []

        def close_active_windows(self, skip_titles=None):
            self.closed += 1

        def open_menu_item(self, search_term, match_text, onDemand=True):
            self.open_calls.append((search_term, match_text, onDemand))
            return True

        def maximize_non_rf_windows(self):
            self.maximized += 1

    monkeypatch.setattr("core.detour.NavigationManager", DummyNav)

    class ToolClose:
        def __init__(self):
            self.clicked = False

        def click(self):
            self.clicked = True

    class Window:
        def __init__(self):
            self.tool = ToolClose()

        def locator(self, _selector):
            return SimpleNamespace(first=self.tool)

    class WindowLocator:
        def __init__(self):
            self.last = Window()

        def count(self):
            return 1

    wait_calls = []

    class DummyPage:
        def __init__(self):
            self.keyboard = SimpleNamespace(press=lambda key: None)

        def wait_for_timeout(self, ms):
            wait_calls.append(ms)

        def locator(self, selector):
            return WindowLocator()

    detour_page = DummyPage()
    main_page = DummyPage()

    fill_calls = []

    def fill_ilpn_cb(val, page=None, tab_click_timeout_ms=None):
        fill_calls.append((val, tab_click_timeout_ms, page))
        return True

    cfg = {
        "search_term": "tasks",
        "match_text": "Tasks",
        "screenshot_tag": "tagged",
        "entries": [
            {"enabled": True, "close_after_open": True, "fill_ilpn": True, "drill_detail": True, "tab_click_timeout_ms": 1500},
        ],
    }

    result = run_open_ui_detours(
        cfg,
        main_page=main_page,
        screenshot_mgr="ss",
        detour_page=detour_page,
        settings=SimpleNamespace(app=SimpleNamespace(change_warehouse="WH")),
        screen_context={"ilpn": "ILPN123"},
        fill_ilpn_cb=fill_ilpn_cb,
    )

    assert result is True
    assert ensure_calls  # detour readiness called
    assert fill_calls and fill_calls[0][0] == "ILPN123"
    assert wait_calls and 5000 in wait_calls
    assert any("Visited UI" in log for log in rf_logs)


def test_run_open_ui_detours_handles_disabled_and_failure(monkeypatch):
    """Disabled configs should no-op and open failures should short-circuit."""
    # Disabled dict
    assert run_open_ui_detours({"enabled": False}, main_page=None, screenshot_mgr=None) is True

    class DummyNav:
        def __init__(self, page, screenshot_mgr):
            pass

        def close_active_windows(self, skip_titles=None):
            pass

        def open_menu_item(self, search_term, match_text, onDemand=True):
            return False

    monkeypatch.setattr("core.detour.NavigationManager", DummyNav)
    detour_page = SimpleNamespace(wait_for_timeout=lambda ms: None, locator=lambda s: SimpleNamespace(count=lambda: 0))
    assert run_open_ui_detours(
        {"search_term": "bad", "match_text": "Bad"}, main_page=detour_page, screenshot_mgr=None
    ) is False
