"""Lightweight coverage for iLPN filter helper behavior."""
import sys
from io import BytesIO
from types import SimpleNamespace

from operations.inbound import ilpn_filter_helper as helper


class FakeLocator:
    def __init__(self, page, name):
        self.page = page
        self.name = name
        self.press_calls = []

    @property
    def first(self):
        return self

    def wait_for(self, *args, **kwargs):
        if getattr(self.page, "fail_waits", False):
            raise Exception("wait failed")
        return self

    def evaluate(self, *args, **kwargs):
        self.page.evaluate_calls.append((self.name, args, kwargs))
        return {
            "display": "block",
            "visibility": "visible",
            "disabled": False,
            "readonly": False,
        }

    def click(self, *args, **kwargs):
        self.page.clicks.append(self.name)

    def fill(self, value):
        self.page.fills.append((self.name, value))

    def press(self, key):
        self.press_calls.append(key)
        self.page.presses.append((self.name, key))

    def locator(self, selector):
        return FakeLocator(self.page, selector)


class FakePage:
    def __init__(self, *, fail_locators=False, fail_waits=False, eval_result=True):
        self.fail_locators = fail_locators
        self.fail_waits = fail_waits
        self.eval_result = eval_result
        self.frames = []
        self.locator_calls = []
        self.clicks = []
        self.fills = []
        self.presses = []
        self.evaluate_calls = []

    def locator(self, selector):
        self.locator_calls.append(selector)
        if self.fail_locators:
            raise Exception("no locator available")
        return FakeLocator(self, selector)

    def get_by_role(self, role, name=None):
        label = f"{role}:{name}"
        self.locator_calls.append(label)
        return FakeLocator(self, label)

    def press(self, *args):
        self.presses.append(args)

    def type(self, *args):
        self.presses.append(("type", args))

    def evaluate(self, script, *args):
        self.evaluate_calls.append((script, args))
        return self.eval_result

    def wait_for_timeout(self, *_args, **_kwargs):
        return None


class FakeFrame(SimpleNamespace):
    def __init__(self, url):
        super().__init__(url=url)


def test_find_ilpn_frame_prefers_uxiframe():
    page = SimpleNamespace(
        frames=[
            FakeFrame("https://example.com/blank"),
            FakeFrame("https://example.com/lpnlist"),
            FakeFrame("https://example.com/uxiframe/detail"),
        ]
    )

    frame = helper._find_ilpn_frame(page)
    assert frame.url.endswith("/uxiframe/detail")


def test_fill_ilpn_filter_visible_input_flow(monkeypatch):
    page = FakePage()
    captured = {}

    def fake_open(target, ilpn, **_kwargs):
        captured["target"] = target
        captured["ilpn"] = ilpn
        return True

    monkeypatch.setattr(helper, "_open_single_filtered_ilpn_row", fake_open)
    monkeypatch.setattr(helper, "_find_ilpn_frame", lambda p: None)

    assert helper.fill_ilpn_filter(page, "LPN123") is True
    assert captured["ilpn"] == "LPN123"
    assert any("filter" in sel for sel in page.locator_calls)
    assert ("button:Apply" in page.clicks)
    assert ("LPN123" in [val for _name, val in page.fills])


def test_fill_ilpn_filter_hidden_fill_fallback(monkeypatch):
    page = FakePage(fail_waits=True, eval_result=True)

    monkeypatch.setattr(helper, "_open_single_filtered_ilpn_row", lambda *a, **k: True)
    monkeypatch.setattr(helper, "_find_ilpn_frame", lambda p: None)

    assert helper.fill_ilpn_filter(page, "HIDDEN1") is True
    assert page.evaluate_calls, "hidden fill should evaluate candidate inputs"
    assert any("debug_ilpn_filter" in call[0] for call in page.evaluate_calls)
    assert any("Enter" in args for args in page.presses if isinstance(args, tuple))


def test_wait_for_ext_mask_detects_clear(monkeypatch):
    class Mask:
        def __init__(self):
            self.counts = [2, 1, 0]

        def count(self):
            return self.counts.pop(0)

    class Target:
        def __init__(self):
            self.waits = []
            self.mask = Mask()

        def locator(self, _sel):
            return self.mask

        def wait_for_timeout(self, ms):
            self.waits.append(ms)

    target = Target()
    assert helper._wait_for_ext_mask(target, timeout_ms=1000) is True
    assert target.waits, "should wait at least once"


def test_wait_for_ext_mask_timeout_zero():
    class Mask:
        def count(self):
            return 1

    class Target:
        def locator(self, _sel):
            return Mask()

        def wait_for_timeout(self, _ms):
            pass

    assert helper._wait_for_ext_mask(Target(), timeout_ms=0) is True


def test_compute_view_hash_uses_evaluate():
    class Target:
        def evaluate(self, script):
            assert "innerText" in script
            return "hello"

    h = helper._compute_view_hash(Target())
    assert h is not None and len(h) == 40


def test_compute_view_hash_handles_exception():
    class Target:
        def evaluate(self, _):
            raise RuntimeError("boom")

    assert helper._compute_view_hash(Target()) is None


def test_wait_for_stable_view(monkeypatch):
    hashes = iter(["a", "a", "a"])
    monkeypatch.setattr(helper, "_compute_view_hash", lambda _t: next(hashes, "a"))
    target = SimpleNamespace(wait_for_timeout=lambda *_a, **_k: None)
    assert helper._wait_for_stable_view(target, stable_samples=2, interval_ms=1, timeout_ms=10) is True


def test_wait_for_stable_view_timeout(monkeypatch):
    monkeypatch.setattr(helper, "_compute_view_hash", lambda _t: None)
    target = SimpleNamespace(wait_for_timeout=lambda *_a, **_k: None)
    assert helper._wait_for_stable_view(target, stable_samples=2, interval_ms=1, timeout_ms=1) is False


def test_ext_store_count_success_and_failure():
    class TargetOK:
        def evaluate(self, _):
            return 3

    class TargetFail:
        def evaluate(self, _):
            raise RuntimeError("boom")

    assert helper._ext_store_count(TargetOK()) == 3
    assert helper._ext_store_count(TargetFail()) is None


def test_ext_open_first_row_paths():
    class TargetOK:
        def evaluate(self, _):
            return True

    class TargetFail:
        def evaluate(self, _):
            raise RuntimeError("fail")

    assert helper._ext_open_first_row(TargetOK()) is True
    assert helper._ext_open_first_row(TargetFail()) is False


def test_statusbar_count_parses_text():
    class Bar:
        def inner_text(self, timeout=None):
            assert timeout == 800
            return "Displaying 1 - 1 of 5"

    class Target:
        def __init__(self):
            self.bar = Bar()

        def locator(self, _sel):
            return self

        @property
        def last(self):
            return self.bar

    assert helper._statusbar_count(Target()) == 5


def test_statusbar_count_handles_exception():
    class Target:
        def locator(self, _sel):
            raise RuntimeError("no locator")

    assert helper._statusbar_count(Target()) is None


def test_statusbar_count_handles_non_int():
    class Bar:
        def inner_text(self, timeout=None):
            return "of many"

    class Target:
        @property
        def last(self):
            return Bar()

        def locator(self, _sel):
            return self

    assert helper._statusbar_count(Target()) is None


def test_find_ilpn_frame_handles_bad_urls():
    class BadFrame:
        @property
        def url(self):
            raise RuntimeError("no url")

    page = SimpleNamespace(frames=[BadFrame()])
    frame = helper._find_ilpn_frame(page)
    assert frame is None


def test_dom_open_ilpn_row_success_and_failure(monkeypatch):
    # Success payload
    class Target:
        def __init__(self, payload):
            self.payload = payload
            self.calls = []

        def evaluate(self, _script, _ilpn):
            self.calls.append(_ilpn)
            if isinstance(self.payload, Exception):
                raise self.payload
            return self.payload

    success_payload = {"ok": True, "tableIdx": 1, "rowIdx": 0, "iframeId": "f1"}
    assert helper._dom_open_ilpn_row(Target(success_payload), "ILPN1") is True

    failure_payload = {"ok": False, "reason": "no_match", "tables": 0}
    assert helper._dom_open_ilpn_row(Target(failure_payload), "ILPN2") is False

    error_target = Target(RuntimeError("fail"))
    assert helper._dom_open_ilpn_row(error_target, "ILPN3") is False

    none_target = Target(None)
    assert helper._dom_open_ilpn_row(none_target, "ILPN4") is False


def test_maximize_page_for_capture_exercises_paths():
    calls = {"ready": []}

    class Page:
        def __init__(self):
            self.waits = []
            self.front = 0

        def evaluate(self, script):
            calls["ready"].append(script)
            if "readyState" in script:
                return "complete"
            return None

        def wait_for_timeout(self, ms):
            self.waits.append(ms)

        def bring_to_front(self):
            self.front += 1

    page = Page()
    helper._maximize_page_for_capture(page)
    assert page.front == 1
    assert any("readyState" in s for s in calls["ready"])


def test_diagnose_tabs_handles_exceptions(monkeypatch):
    monkeypatch.setattr(helper.Settings.app, "app_verbose_logging", True)

    class Frames:
        def __len__(self):
            raise RuntimeError("len failed")

    class Target:
        frames = Frames()

        def evaluate(self, _):
            raise RuntimeError("eval fail")

    helper._diagnose_tabs(Target())


def test_click_ilpn_detail_tabs_basic(monkeypatch):
    # Skip diagnostics to keep fake minimal
    monkeypatch.setattr(helper.Settings.app, "app_verbose_logging", False)

    class Element:
        def __init__(self):
            self.clicked = False

        def scroll_into_view_if_needed(self, *_, **__):
            return None

        def click(self, *_, **__):
            self.clicked = True

    class Elements:
        def __init__(self):
            self.e = Element()

        def count(self):
            return 1

        def nth(self, _i):
            return self.e

    class Target:
        def __init__(self):
            self.frames = []
            self.tab_elements = Elements()

        def get_by_text(self, _text, exact=True):
            return self.tab_elements

        def wait_for_timeout(self, *_a, **_k):
            return None

    page = Target()
    assert helper._click_ilpn_detail_tabs(page, capture_after_tabs=False) is True
    assert page.tab_elements.e.clicked is True


def test_click_ilpn_detail_tabs_capture_fallback(monkeypatch):
    monkeypatch.setattr(helper.Settings.app, "app_verbose_logging", False)

    class Target:
        def __init__(self):
            self.frames = None

        def wait_for_timeout(self, *_a, **_k):
            return None

        def get_by_text(self, *_a, **_k):
            return SimpleNamespace(count=lambda: 0)

    class ScreenshotMgr:
        def __init__(self):
            self.captured = 0

        def capture(self, *_a, **_k):
            self.captured += 1

    mgr = ScreenshotMgr()
    assert helper._click_ilpn_detail_tabs(Target(), mgr, capture_after_tabs=True) is True
    assert mgr.captured == 1


def test_click_ilpn_detail_tabs_with_overlay(monkeypatch, tmp_path):
    monkeypatch.setattr(helper.Settings.app, "app_verbose_logging", True)

    # Fake minimal PIL stack
    class FakeFont:
        def getbbox(self, text):
            return (0, 0, max(1, len(text)), 10)

    class FakeDraw:
        def __init__(self, img):
            self.img = img

        def rectangle(self, *_, **__):
            return None

        def text(self, *_, **__):
            return None

    class FakeImg:
        def __init__(self, size=(4, 4)):
            self.size = size
            self.width, self.height = size

        def paste(self, *_, **__):
            return None

        def convert(self, *_a, **_k):
            return self

        def save(self, filename, format=None, **_kwargs):
            with open(filename, "wb") as f:
                f.write(b"fakeimg")

        def getbbox(self, *_):
            return (0, 0, self.width, self.height)

    class FakeImageModule:
        @staticmethod
        def new(_mode, size, _color):
            return FakeImg(size)

        @staticmethod
        def open(_bytes):
            return FakeImg()

        @staticmethod
        def alpha_composite(img1, img2):
            return img1

    class FakeImageDrawModule:
        @staticmethod
        def Draw(img):
            return FakeDraw(img)

    class FakeImageFontModule:
        @staticmethod
        def load_default():
            return FakeFont()

    monkeypatch.setitem(
        sys.modules,
        "PIL",
        SimpleNamespace(Image=FakeImageModule, ImageDraw=FakeImageDrawModule, ImageFont=FakeImageFontModule),
    )
    monkeypatch.setitem(sys.modules, "PIL.Image", FakeImageModule)
    monkeypatch.setitem(sys.modules, "PIL.ImageDraw", FakeImageDrawModule)
    monkeypatch.setitem(sys.modules, "PIL.ImageFont", FakeImageFontModule)

    class Element:
        def __init__(self):
            self.clicked = False

        def scroll_into_view_if_needed(self, *_, **__):
            return None

        def click(self, *_, **__):
            self.clicked = True

    class Elements:
        def __init__(self):
            self.e = Element()

        def count(self):
            return 1

        def nth(self, _i):
            return self.e

    class Frame:
        def __init__(self, url):
            self.url = url

        def evaluate(self, _):
            return {"potentialTabs": [{"text": "Header"}], "totalElements": 1}

    class Target:
        def __init__(self):
            self.frames = [Frame("https://frame")]
            self.tab_elements = Elements()
            self.page = self

        def get_by_text(self, _text, exact=True):
            return self.tab_elements

        def wait_for_timeout(self, *_a, **_k):
            return None

        def evaluate(self, _script):
            return {"potentialTabs": [], "totalElements": 0}

        def screenshot(self, **_kwargs):
            return b"img-bytes"

    class ScreenshotMgr:
        def __init__(self, base_dir):
            self.sequence = 0
            self.image_format = "jpeg"
            self.image_quality = 80
            self.current_scenario_label = "scenario"
            self.current_stage_label = "stage"
            self.saved = []
            self.base_dir = base_dir

        def _build_filename(self, name):
            path = self.base_dir / f"{name}.jpg"
            self.saved.append(path)
            return path

        def capture(self, *_a, **_k):
            self.saved.append(self.base_dir / "capture.jpg")

    mgr = ScreenshotMgr(tmp_path)
    target = Target()
    assert helper._click_ilpn_detail_tabs(target, mgr) is True
    assert mgr.sequence == 1
    assert mgr.saved, "should have saved at least one file"


def test_open_single_filtered_ilpn_row_ext_path(monkeypatch):
    calls = {}

    def fake_dom_open(target, ilpn):
        calls["dom"] = ilpn
        return False

    def fake_ext_open(target):
        calls["ext_open"] = True
        return True

    def fake_click_tabs(target, **_kwargs):
        calls["tabs"] = True
        return True

    monkeypatch.setattr(helper, "_dom_open_ilpn_row", fake_dom_open)
    monkeypatch.setattr(helper, "_ext_store_count", lambda _t: 1)
    monkeypatch.setattr(helper, "_statusbar_count", lambda _t: None)
    monkeypatch.setattr(helper, "_ext_open_first_row", fake_ext_open)
    monkeypatch.setattr(helper, "_click_ilpn_detail_tabs", fake_click_tabs)

    class Mask:
        def count(self):
            return 0

    class Target:
        def __init__(self):
            self.keyboard = SimpleNamespace(press=lambda *_a, **_k: None)

        def locator(self, _sel):
            return Mask()

        def wait_for_timeout(self, *_a, **_k):
            return None

    assert helper._open_single_filtered_ilpn_row(Target(), "ILPNA") is True
    assert calls["ext_open"] is True and calls["tabs"] is True


def test_open_single_filtered_ilpn_row_dom_first(monkeypatch):
    monkeypatch.setattr(helper, "_dom_open_ilpn_row", lambda *_a, **_k: True)
    monkeypatch.setattr(helper, "_click_ilpn_detail_tabs", lambda *_a, **_k: True)
    class Target:
        def locator(self, _sel):
            return SimpleNamespace(count=lambda: 0)

        def wait_for_timeout(self, *_a, **_k):
            return None

    target = Target()
    assert helper._open_single_filtered_ilpn_row(target, "ILPNC") is True


def test_open_single_filtered_ilpn_row_locator_path(monkeypatch):
    calls = {"double": 0}

    monkeypatch.setattr(helper, "_dom_open_ilpn_row", lambda *_a, **_k: False)
    monkeypatch.setattr(helper, "_ext_store_count", lambda _t: 0)
    monkeypatch.setattr(helper, "_statusbar_count", lambda _t: None)
    monkeypatch.setattr(helper, "_ext_open_first_row", lambda _t: False)
    monkeypatch.setattr(helper, "_click_ilpn_detail_tabs", lambda *_a, **_k: True)

    monkeypatch.setattr(helper, "_wait_for_stable_view", lambda *_a, **_k: True)

    class Row:
        def __init__(self):
            self.clicked = False

        def click(self, *_, **__):
            self.clicked = True

        def dblclick(self, *_, **__):
            calls["double"] += 1

        def press(self, *_a, **_k):
            calls["pressed"] = True

    class Rows:
        @property
        def first(self):
            return Row()

        def count(self):
            return 1

    class Grid:
        @property
        def last(self):
            return self

        def wait_for(self, *_, **__):
            return self

        def locator(self, _sel):
            return Rows()

    class Target:
        def __init__(self):
            self.keyboard = SimpleNamespace(press=lambda *_a, **_k: None)

        def wait_for_timeout(self, *_a, **_k):
            return None

        def locator(self, _sel):
            return Grid()

    assert helper._open_single_filtered_ilpn_row(Target(), "ILPNB") is True
    assert calls["double"] >= 1
