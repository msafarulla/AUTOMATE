import html
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, Tuple

from playwright.sync_api import Frame, Locator, Page, Response, TimeoutError

from core.screenshot import ScreenshotManager
from utils.hash_utils import HashUtils
from utils.wait_utils import WaitUtils
from core.logger import app_log


class PostMessageManager:
    """Encapsulates interactions with the Post Message (Integration) screen."""

    ERROR_MARKERS = ("error", "failed", "exception", "invalid")
    SUCCESS_RESP_CODES = {"", "0", "25"}

    def __init__(self, page: Page, screenshot_mgr: ScreenshotManager):
        self.page = page
        self.screenshot_mgr = screenshot_mgr
        self._reset_required = False
        self._last_sent_snapshot: str | None = None

    def send_message(self, message: str) -> Tuple[bool, Dict[str, Any]]:

        frame = self._resolve_frame()

        self._fill_message(frame, message)
        response_info = self._submit_and_capture(frame)
        last_response = response_info

        if not response_info["is_error"]:
            # self._release_post_message_focus(frame)
            # self._mark_reset_required(message)
            return True, response_info

        app_log(f"⚠️ Post Message attempt failed: {response_info['summary']}")
        return False, last_response

    def _resolve_frame(self, timeout_ms: int = 8000, poll_interval_ms: int = 200) -> Frame:
        """Wait for the frame that hosts the Post Message UI to become available."""
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            for frame in self.page.frames:
                if self._has_visible_textarea(frame):
                    return frame
            if time.monotonic() >= deadline:
                break
            self.page.wait_for_timeout(poll_interval_ms)

        app_log("⚠️ Falling back to main frame; Post Message textarea not detected in any iframe.")
        return self.page.main_frame

    def _has_visible_textarea(self, frame: Frame) -> bool:
        try:
            locator = frame.locator("textarea:visible")
            return locator.count() > 0
        except Exception:
            return False

    def _fill_message(self, frame: Frame, message: str):
        textarea = self._locate_textarea(frame)
        textarea.click()
        textarea.fill(message)

        truncated = (message[:40] + "...") if len(message) > 40 else message
        self.screenshot_mgr.capture(
            self.page,
            f"post_message_ready",
            f"Attempt : {truncated}",
        )

    def _submit_and_capture(self, frame: Frame) -> Dict[str, Any]:
        send_button = self._locate_send_button(frame)
        prev_snapshot = HashUtils.get_frame_snapshot(frame)
        response_text = None
        try:
            with frame.expect_response(self._is_post_message_response, timeout=20000) as response_ctx:
                send_button.click()
            response_text = self._extract_response_text(response_ctx.value)
        except TimeoutError:
            # fallback to DOM reading if we don't detect the network response
            pass

        WaitUtils.wait_for_screen_change(frame, prev_snapshot)
        if not response_text:
            self._wait_for_response_text_stable(frame)
            response_text = self._read_response(frame)

        response = response_text or ""
        info = self._interpret_response(response)
        label = "Success" if not info["is_error"] else "Error"
        self.screenshot_mgr.capture(
            self.page,
            f"post_message_response_{label.lower()}",
            f"{label}: {info['summary'][:60]}",
        )
        return info

    def _reset_form(self, frame: Frame):
        reset_button = self._locate_reset_button(frame)
        prev_snapshot = HashUtils.get_frame_snapshot(frame)
        reset_button.click()
        WaitUtils.wait_for_screen_change(frame, prev_snapshot)
        self.screenshot_mgr.capture(
            self.page,
            "post_message_reset",
            "Reset form after error",
        )

    def _mark_reset_required(self, message: str):
        self._reset_required = True
        self._last_sent_snapshot = message.strip()

    def _ensure_reset_before_post(self, frame: Frame, message: str) -> dict[str, Any] | None:
        if not self._reset_required:
            return None

        textarea = self._locate_textarea(frame)
        current_value = textarea.input_value().strip()
        prev_snapshot = self._last_sent_snapshot or ""
        if current_value and current_value == prev_snapshot:
            summary = "Post Message already sent; reset the form before reposting."
            app_log(f"⚠️ {summary}")
            return {
                "raw": "",
                "summary": summary,
                "payload": {},
                "is_error": True,
            }

        self._reset_required = False
        self._last_sent_snapshot = None
        return None

    def _locate_textarea(self, frame: Frame) -> Locator:
        selectors = [
            "textarea[name='dataForm:xmlString']",
            "textarea[id='dataForm:xmlString']",
            "textarea[name*='xmlString' i]",
            "textarea[id*='xmlString' i]",
            "textarea[name*='xml' i]",
            "textarea[id*='xml' i]",
            "textarea[name*='message' i]",
            "textarea[id*='message' i]",
            "textarea[data-ref*='message' i]",
            "textarea[data-componentid*='message' i]",
            "textarea:visible",
        ]

        for selector in selectors:
            locator = frame.locator(selector).first
            try:
                locator.wait_for(state="visible", timeout=3000)
                return locator
            except Exception:
                continue

        raise RuntimeError("Unable to locate Post Message textarea")

    def _locate_send_button(self, frame: Frame) -> Locator:
        candidates = [
            frame.locator("input#dataForm\\:postMessageCmdId"),
            frame.get_by_role("button", name=re.compile(r"send", re.IGNORECASE)),
            frame.locator("a.x-btn:has-text('Send')"),
            frame.locator("button:has-text('Send')"),
            frame.locator("text=/\\bSend\\b/i"),
        ]

        for locator in candidates:
            candidate = locator.first
            try:
                candidate.wait_for(state="visible", timeout=3000)
                return candidate
            except Exception:
                continue

        raise RuntimeError("Unable to locate the Send button on Post Message screen")

    def _locate_reset_button(self, frame: Frame) -> Locator:
        candidates = [
            frame.get_by_role("button", name=re.compile(r"reset", re.IGNORECASE)),
            frame.locator("a.x-btn:has-text('Reset')"),
            frame.locator("button:has-text('Reset')"),
            frame.locator("text=/\\bReset\\b/i"),
        ]

        for locator in candidates:
            candidate = locator.first
            try:
                candidate.wait_for(state="visible", timeout=3000)
                return candidate
            except Exception:
                continue

        raise RuntimeError("Unable to locate the Reset button on Post Message screen")

    def _release_post_message_focus(self, frame: Frame):
        try:
            frame.evaluate(
                "() => { const textarea = document.querySelector(\"textarea[name*='message' i]\"); textarea?.blur(); }"
            )
        except Exception:
            pass
        try:
            self.page.keyboard.press("Escape")
        except Exception:
            pass
        try:
            self.page.wait_for_timeout(300)
        except Exception:
            pass

    def _wait_for_response_text_stable(self, frame: Frame, timeout_ms: int = 20000, stable_ms: int = 700):
        locator = frame.locator("textarea[name='dataForm:resultString']").first
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
        except Exception:
            return

        try:
            last_value = locator.input_value()
        except Exception:
            return

        stable_deadline = time.monotonic() + stable_ms / 1000
        end_time = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < end_time:
            try:
                current_value = locator.input_value()
            except Exception:
                return

            if current_value != last_value:
                last_value = current_value
                stable_deadline = time.monotonic() + stable_ms / 1000
            elif time.monotonic() >= stable_deadline:
                return

            frame.page.wait_for_timeout(200)

    def _is_post_message_response(self, response: Response) -> bool:
        req = response.request
        post_data = (req.post_data or "").lower()
        if "postmessagecmdid" in post_data:
            return True
        url_lower = response.url.lower()
        if "postmessage" in url_lower or "post-message" in url_lower:
            return True
        return False

    def _extract_response_text(self, response: Response) -> str | None:
        try:
            return response.text()
        except Exception:
            return None

    def _read_response(self, frame: Frame) -> str:
        selectors = [
            "textarea[name='dataForm:resultString']",
            "textarea[id='dataForm:resultString']",
            "textarea[name='resultString']",
            "textarea#resultString",
            "textarea[id*='resultString' i]",
            "textarea[name*='resultString' i]",
            "textarea[name*='response' i]",
            "textarea[id*='response' i]",
            "textarea[data-ref*='response' i]",
            "pre:visible",
            "div[class*='response']:visible",
            "div[data-ref*='response' i]",
        ]

        best_text = ""
        for selector in selectors:
            locator = frame.locator(selector).first
            try:
                locator.wait_for(state="visible", timeout=2000)
                if selector.startswith("textarea"):
                    text = locator.input_value().strip()
                else:
                    text = locator.inner_text().strip()
                if text:
                    unescaped = html.unescape(text)
                    cleaned = re.sub(r"\s+", " ", unescaped)
                    if len(cleaned) > len(best_text):
                        best_text = cleaned
            except Exception:
                continue
        if best_text:
            return best_text

        try:
            text = frame.locator("body").inner_text()
            unescaped = html.unescape(text)
            return re.sub(r"\s+", " ", unescaped.strip())
        except Exception:
            return ""

    def _interpret_response(self, response_text: str) -> Dict[str, Any]:
        info = {
            "raw": response_text or "",
            "summary": (response_text or "").strip() or "Empty response",
            "payload": {},
            "is_error": self._is_error_response(response_text),
        }

        text = (response_text or "").strip()
        if text.startswith("<?xml"):
            try:
                root = ET.fromstring(text)

                def _get(path: str):
                    node = root.find(path)
                    if node is not None and node.text:
                        return node.text.strip()
                    return None

                payload = {
                    "message_type": _get(".//Header/Message_Type"),
                    "internal_id": _get(".//Header/Internal_Reference_ID"),
                    "persistent_state": _get(".//Response/Persistent_State"),
                    "error_type": _get(".//Response/Error_Type"),
                    "resp_code": _get(".//Response/Resp_Code"),
                    "exception_details": _get(".//Response/Response_Details/Exception_Details"),
                    "response_type": _get(".//Application_Advice/Response_Type"),
                    "ack_code": _get(".//Application_Advice/Application_Ackg_Code"),
                    "imported_object_type": _get(".//Application_Advice/Imported_Object_Type"),
                }

                info["payload"] = payload
                info["is_error"] = self._is_xml_error(payload)
                info["summary"] = self._format_response_summary(payload)
            except ET.ParseError:
                pass

        return info

    def _is_error_response(self, response_text: str) -> bool:
        normalized = (response_text or "").lower()
        return any(marker in normalized for marker in self.ERROR_MARKERS)

    def _is_xml_error(self, payload: Dict[str, str]) -> bool:
        error_type = (payload.get("error_type") or "").strip()
        resp_code = (payload.get("resp_code") or "").strip()
        exception = payload.get("exception_details") or ""
        persistent_state = (payload.get("persistent_state") or "").strip()
        ack_code = (payload.get("ack_code") or "").strip().upper()
        response_type = (payload.get("response_type") or "").strip().lower()
        imported_object = (payload.get("imported_object_type") or "").strip().lower()
        is_distribution_order = imported_object == "distributionorder"

        codes_ok = error_type in ("", "0") and resp_code in self.SUCCESS_RESP_CODES
        no_exception = exception.strip() == ""
        persistent_ok = persistent_state in ("", "0", "1")
        ack_ok = ack_code in ("TA", "AA", "OK")
        response_ok = response_type in ("", "confirmation", "accepted")
        distribution_ok = is_distribution_order and (ack_ok or resp_code in self.SUCCESS_RESP_CODES)

        return not (
            (codes_ok or ack_ok or response_ok or distribution_ok)
            and no_exception
            and persistent_ok
        )

    def _format_response_summary(self, payload: Dict[str, str]) -> str:
        resp_code = payload.get("resp_code") or "n/a"
        error_type = payload.get("error_type") or "n/a"
        persistent = payload.get("persistent_state") or "n/a"
        exception = (payload.get("exception_details") or "").replace("\n", " ").strip()

        base = f"RespCode {resp_code}, ErrorType {error_type}, PersistentState {persistent}"
        if exception:
            return f"{base}: {exception}"
        return base
