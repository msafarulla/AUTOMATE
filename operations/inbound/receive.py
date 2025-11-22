"""
Receive Operation - Handles ASN receiving workflow in RF terminal.

Flow: Navigate → Scan ASN → Scan Item → Enter Qty → Confirm Location
"""
import re
import time
from datetime import datetime
from typing import Any, Iterable

from operations.base_operation import BaseOperation
from operations.rf_primitives import RFMenuIntegration
from ui.navigation import NavigationManager
from config.operations_config import OperationConfig
from core.logger import rf_log
from utils.hash_utils import HashUtils
from utils.wait_utils import WaitUtils


class ReceiveOperation(BaseOperation):
    """Handles ASN receiving workflow in RF terminal."""

    def __init__(self, page, page_mgr, screenshot_mgr, rf_menu):
        super().__init__(page, page_mgr, screenshot_mgr, rf_menu)
        
        # Setup RF integration
        integration = RFMenuIntegration(rf_menu)
        self.rf = integration.get_primitives()
        self.workflows = integration.get_workflows()
        
        # Load config
        self.menu = OperationConfig.RECEIVE_MENU
        self.selectors = OperationConfig.RECEIVE_SELECTORS
        self._ilpn: str | None = None
        self._screen_context: dict[str, int | None] | None = None

    def execute(
        self,
        asn: str,
        item: str,
        quantity: int,
        *,
        flow_hint: str | None = None,
        auto_handle: bool = False,
        open_ui_cfg: dict[str, Any] | None = None,
    ) -> bool:
        """
        Execute receive operation.
        
        Args:
            asn: ASN number to receive
            item: Item barcode
            quantity: Quantity to receive
            flow_hint: expected flow after qty
            auto_handle: whether to auto-handle deviations
            open_ui_cfg: optional UI detours (Tasks/iLPNs) from workflow config
        """
        steps = [
            (self._navigate, "Navigate to receive"),
            (lambda: self._scan(asn, item), "Scan ASN/Item"),
            (lambda: self._enter_quantity(quantity, item, open_ui_cfg), "Enter quantity"),
            (lambda: self._complete(asn, item, quantity, flow_hint, auto_handle), "Complete receive"),
        ]
        
        for step_fn, step_name in steps:
            if not step_fn():
                rf_log(f"❌ Failed at: {step_name}")
                return False
        return True

    # =========================================================================
    # MAIN STEPS
    # =========================================================================

    def _navigate(self) -> bool:
        """Step 1: Navigate to receive menu."""
        return self.workflows.navigate_to_menu_by_search(
            self.menu.search_term, 
            self.menu.tran_id
        )

    def _scan(self, asn: str, item: str) -> bool:
        """Step 2: Scan ASN and item barcodes."""
        scans = [
            (self.selectors.asn, asn, "ASN"),
            (self.selectors.item, item, "Item"),
        ]
        
        for selector, value, label in scans:
            has_error, msg = self.workflows.scan_barcode_auto_enter(
                selector, value, label
            )
            if has_error:
                rf_log(f"❌ {label} scan failed: {msg}")
                return False
        shipped, received, ilpn = self._log_screen_values()
        self._ilpn = ilpn
        self._screen_context = {"shipped": shipped, "received": received, "ilpn": ilpn}
        return True

    def _enter_quantity(
        self,
        quantity: int,
        item: str,
        open_ui_cfg: dict[str, Any] | None,
    ) -> bool:
        """Step 3: Enter quantity."""
        if self._screen_context:
            rf_log(
                f"ℹ️ Entering qty with context shipped={self._screen_context.get('shipped')} "
                f"received={self._screen_context.get('received')} "
                f"ilpn={self._screen_context.get('ilpn')}"
            )
        success = self.workflows.enter_quantity(
            self.selectors.quantity,
            quantity,
            item_name=item,
            context=self._screen_context,
        )

        if success:
            success = self._maybe_run_open_ui(open_ui_cfg)
        return success

    def _complete(
        self,
        asn: str,
        item: str,
        quantity: int,
        flow_hint: str | None,
        auto_handle: bool,
    ) -> bool:
        """Step 4: Handle post-quantity flow."""
        # Check current screen
        detected = self._detect_flow(flow_hint)
        
        # Handle deviation if needed
        if detected != flow_hint:
            rf_log(f"⚠️ Flow mismatch: expected {flow_hint}, got {detected}")
            self._capture_deviation(detected, auto_handle)
            if not auto_handle:
                return False
            return self._handle_deviation(detected)

        # Happy path: confirm location
        location = self._read_location()
        self.workflows.confirm_location(self.selectors.location, location)
        self._capture_success(asn, item, quantity)
        return True

    # =========================================================================
    # OPTIONAL TASKS UI DETOUR
    # =========================================================================

    def _maybe_run_open_ui(self, open_ui_cfg: dict[str, Any] | list[dict[str, Any]] | None) -> bool:
        """Open one or more configured UIs mid-flow (e.g., Tasks or iLPNs)."""
        if not open_ui_cfg:
            return True

        # Normalize to a list of entries
        entries: list[dict[str, Any]] = []
        base_cfg: dict[str, Any] = {}
        if isinstance(open_ui_cfg, list):
            entries = open_ui_cfg
        elif isinstance(open_ui_cfg, dict):
            if not bool(open_ui_cfg.get("enabled", True)):
                return True
            base_cfg = open_ui_cfg
            entries = open_ui_cfg.get("entries") or [open_ui_cfg]
        else:
            return True

        nav_mgr = NavigationManager(self.page, self.screenshot_mgr)
        focus_title = base_cfg.get("rf_focus_title", "RF Menu")

        keep_ui_open = False
        default_post_fill = base_cfg.get("post_fill_ms")
        default_post_screenshot = base_cfg.get("post_screenshot_tag")
        default_ilpn_wait = base_cfg.get("ilpn_wait_ms")

        for idx, entry in enumerate(entries, 1):
            if not entry or not bool(entry.get("enabled", True)):
                continue

            search_term = entry.get("search_term") or base_cfg.get("search_term", "tasks")
            match_text = entry.get("match_text") or base_cfg.get("match_text", "Tasks (Configuration)")
            close_existing = bool(entry.get("close_existing", base_cfg.get("close_existing", True)))
            if not nav_mgr.open_menu_item(search_term, match_text, close_existing=close_existing):
                rf_log(f"❌ UI detour #{idx} failed during receive flow.")
                return False

            operation_note = (
                entry.get("operation_note")
                or base_cfg.get("operation_note")
                or f"Visited UI #{idx} during receive"
            )
            screenshot_tag = (
                entry.get("screenshot_tag")
                or base_cfg.get("screenshot_tag")
                or f"receive_open_ui_{idx}"
            )
            self.screenshot_mgr.capture(self.page, screenshot_tag, operation_note)

            focus_title = entry.get("rf_focus_title") or focus_title
            rf_log(f"ℹ️ {operation_note}")

            if entry.get("fill_ilpn") and self._screen_context and self._screen_context.get("ilpn"):
                ilpn_val = self._screen_context.get("ilpn")
                if not self._fill_ilpn_quick_filter(str(ilpn_val)):
                    return False
                wait_ms = entry.get("ilpn_wait_ms") or default_ilpn_wait or 4000
                self._wait_for_ilpn_apply(wait_ms, operation_note, entry, default_post_screenshot)

            pause_ms = entry.get("pause_ms") or base_cfg.get("pause_ms")
            if pause_ms:
                try:
                    self.page.wait_for_timeout(int(pause_ms))
                except Exception:
                    pass

            # Close the just-opened UI before moving to the next (unless caller wants to preserve)
            preserve = bool(entry.get("preserve_window") or entry.get("preserve"))
            keep_ui_open = keep_ui_open or preserve
            if not preserve:
                nav_mgr.close_active_windows(skip_titles=[focus_title])
        if not keep_ui_open:
            nav_mgr.close_active_windows(skip_titles=[focus_title])

        return True

    # =========================================================================
    # FLOW DETECTION & HANDLING
    # =========================================================================

    def _detect_flow(self, default: str | None) -> str:
        """Detect current screen based on keywords."""
        try:
            body = self.rf.read_field("body").lower()
        except Exception:
            return default or "UNKNOWN"

        for name, meta in OperationConfig.RECEIVE_FLOW_METADATA.items():
            if name == "UNKNOWN":
                continue
            if any(kw in body for kw in meta.get("keywords", [])):
                return name
        
        return default or "UNKNOWN"

    def _handle_deviation(self, flow: str) -> bool:
        """Handle non-happy-path flows."""
        handlers = {
            "IB_RULE_EXCEPTION_BLIND_ILPN": self._handle_blind_ilpn,
        }
        handler = handlers.get(flow)
        if handler:
            return handler()
        rf_log(f"⚠️ No handler for flow: {flow}")
        return False

    def _handle_blind_ilpn(self) -> bool:
        """Handle IB rule exception requiring LPN entry."""
        lpn = datetime.now().strftime("%y%m%d%H%M%S")
        selectors = OperationConfig.RECEIVE_DEVIATION_SELECTORS
        
        for selector in (selectors.lpn_input, selectors.lpn_input_name):
            try:
                has_error, _ = self.rf.fill_and_submit(
                    selector, lpn, "blind_ilpn", f"Entered LPN: {lpn}"
                )
                if not has_error:
                    self.screenshot_mgr.capture_rf_window(
                        self.page, "ilpn_success", "Blind iLPN entered"
                    )
                    return True
            except Exception:
                continue
        
        rf_log("❌ Could not enter blind iLPN")
        return False

    # =========================================================================
    # HELPERS - Reading screen data
    # =========================================================================

    def _read_location(self) -> str:
        """Read suggested location from screen."""
        # Try configured selectors
        for key in ("suggested_location_aloc", "suggested_location_cloc"):
            selector = self.selectors.selectors.get(key)
            if not selector:
                continue
            try:
                loc = self.rf.read_field(selector).replace("-", "").strip()
                if loc:
                    return loc
            except Exception:
                continue

        # Fallback: parse from body
        try:
            body = self.rf.read_field("body")
            match = re.search(r"[AC]LOC\s*:?\s*([A-Za-z0-9\-]+)", body, re.I)
            if match:
                return match.group(1).replace("-", "").strip()
        except Exception:
            pass

        rf_log("⚠️ Could not read suggested location")
        return ""

    def _log_screen_values(self):
        """Log shipped/received quantities (and iLPN) from screen."""
        shipped, received = self._parse_quantities()
        ilpn = self._parse_ilpn()
        rf_log(f"ℹ️ Shipped: {shipped}, Received: {received}, LPN: {ilpn}")
        return shipped, received, ilpn

    def _parse_quantities(self) -> tuple[int | None, int | None]:
        """Extract shipped/received quantities."""
        s = self.selectors.selectors
        shipped = self._read_number(s.get("shipped_quantity"))
        received = self._read_number(s.get("received_quantity"))
        
        if shipped is None and received is None:
            # Fallback: parse body text
            try:
                body = self.rf.read_field("body")
                shipped = self._extract_number(body, r"Shpd?\s*:?\s*([\d,]+)")
                received = self._extract_number(body, r"Rcvd?\s*:?\s*([\d,]+)")
            except Exception:
                pass
        return shipped, received

    def _parse_ilpn(self) -> str | None:
        """Extract iLPN from screen or body."""
        sel = self.selectors.selectors
        ilpn_selector = sel.get("ilpn") or sel.get("ilpn_hidden")
        if ilpn_selector:
            try:
                text = self.rf.read_field(ilpn_selector)
                ilpn = self._extract_lpn(text)
                if ilpn:
                    return ilpn
            except Exception:
                pass

        try:
            body = self.rf.read_field("body")
            ilpn = self._extract_lpn(body)
            if ilpn:
                return ilpn
        except Exception:
            pass
        return None

    def _read_number(self, selector: str | None) -> int | None:
        """Read number from selector."""
        if not selector:
            return None
        try:
            text = self.rf.read_field(selector)
            return self._extract_number(text, r"([\d,]+)")
        except Exception:
            return None

    def _extract_number(self, text: str, pattern: str) -> int | None:
        """Extract first number matching pattern."""
        match = re.search(pattern, text, re.I)
        if match:
            try:
                return int(match.group(1).replace(",", ""))
            except ValueError:
                pass
        return None

    def _extract_lpn(self, text: str) -> str | None:
        """Extract LPN/id from provided text."""
        patterns = [
            r"\bLPN[:\s\"]*([A-Za-z0-9]+)",
            r"\bcaseinpid\b.*?value=\"([A-Za-z0-9]+)\"",
        ]
        normalized = " ".join(text.split())
        for pattern in patterns:
            match = re.search(pattern, normalized, re.I)
            if match:
                return match.group(1).strip()
        return None

    # =========================================================================
    # UI HELPERS
    # =========================================================================

    def _fill_ilpn_quick_filter(self, ilpn: str) -> bool:
        """Fill the iLPN quick filter input and click Apply in the iLPNs UI."""
        # Locate the correct frame (the iLPNs window often runs in its own frame/window).
        target_frame = self._find_ilpn_frame(timeout_ms=6000)
        if not target_frame:
            rf_log("❌ Unable to locate iLPNs frame/window; skipping iLPN fill to avoid typing into RF.")
            return False

        target = target_frame

        # Wait for any in-frame loading mask to clear before interacting
        try:
            mask = target.locator("div.x-mask:visible")
            mask.wait_for(state="hidden", timeout=4000)
        except Exception:
            pass

        candidates = [
            "//span[contains(translate(normalize-space(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'quick filter')]/following::input[1]",
            "//label[contains(translate(normalize-space(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'lpn')]/following::input[1]",
            "//input[contains(@placeholder,'ilter') and not(@type='hidden')]",
            "//input[contains(@aria-label,'Quick filter') and not(@type='hidden')]",
            "//input[contains(@name,'lpn') and not(@type='hidden')]",
            "//input[contains(@id,'lpn') and not(@type='hidden')]",
            "//input[contains(@name,'filter') and not(@type='hidden')]",
            "input.x-form-text:visible",
        ]
        input_field = None
        for sel in candidates:
            try:
                locator = target.locator(sel).first
                locator.wait_for(state="visible", timeout=3000)
                input_field = locator
                break
            except Exception:
                continue

        if not input_field:
            rf_log("⚠️ Could not locate visible iLPN quick filter input, attempting hidden-fill fallback.")

            try:
                filled = target.evaluate(
                    """
                    (ilpn) => {
                        const val = String(ilpn);
                        const inputs = Array.from(document.querySelectorAll('input'));
                        if (!inputs.length) return false;

                        const score = (el) => {
                            const txt = [
                                el.name || '',
                                el.id || '',
                                el.placeholder || '',
                                el.getAttribute('aria-label') || ''
                            ].join(' ').toLowerCase();
                            let s = 0;
                            if (txt.includes('lpn')) s += 3;
                            if (txt.includes('filter')) s += 2;
                            if (el.type === 'hidden') s += 1;
                            return s;
                        };

                        const ranked = inputs
                            .map(el => ({ el, s: score(el) }))
                            .filter(entry => entry.s > 0)
                            .sort((a, b) => b.s - a.s);

                        if (!ranked.length) return false;

                        const el = ranked[0].el;
                        try {
                            el.removeAttribute('disabled');
                            el.style.display = '';
                            el.style.visibility = 'visible';
                            el.style.opacity = '1';
                        } catch (e) {}

                        try { el.focus?.(); } catch (e) {}
                        el.value = val;
                        ['input', 'change', 'keyup', 'keydown', 'keypress'].forEach(evt => {
                            try { el.dispatchEvent(new Event(evt, { bubbles: true, cancelable: true })); } catch (e) {}
                        });

                        const applyBtn = Array.from(document.querySelectorAll('button, a, span')).find(
                            el => /apply/i.test(el.textContent || '')
                        );
                        if (applyBtn) {
                            try { applyBtn.click(); } catch (e) {}
                        }
                        return true;
                    }
                    """,
                    ilpn,
                )
                if filled:
                    try:
                        target.press("body", "Enter")
                        target.press("body", "Space")
                    except Exception:
                        pass

                    # Also try clicking apply via Playwright locators after JS fill
                    apply_candidates = [
                        target.get_by_role("button", name="Apply"),
                        target.locator("//a[.//span[normalize-space()='Apply']]"),
                        target.locator("//button[normalize-space()='Apply']"),
                        target.locator("//span[normalize-space()='Apply']"),
                    ]
                    for btn in apply_candidates:
                        try:
                            btn.first.click()
                            return True
                        except Exception:
                            continue

                    return True
            except Exception as exc:
                rf_log(f"❌ Hidden iLPN fill fallback failed: {exc}")
                return False

            return False

        try:
            input_field.click()
            input_field.fill(ilpn)
            input_field.press("Enter")
        except Exception as exc:
            rf_log(f"❌ Unable to fill iLPN filter: {exc}")
            return False

        apply_candidates = [
            target.get_by_role("button", name="Apply"),
            target.locator("//a[.//span[normalize-space()='Apply']]"),
            target.locator("//button[normalize-space()='Apply']"),
            target.locator("//span[normalize-space()='Apply']"),
        ]
        for btn in apply_candidates:
            try:
                btn.first.click()
                return True
            except Exception:
                continue

        # Keyboard fallback: Tab twice to focus quick filter, type, press Enter then Space for safety
        try:
            target.press("body", "Tab")
            target.press("body", "Tab")
            target.type("body", ilpn)
            target.press("body", "Enter")
            target.press("body", "Space")
            return True
        except Exception as exc:
            rf_log(f"❌ Unable to click Apply in iLPNs UI (even with keyboard fallback): {exc}")
            return False

    def _find_ilpn_frame(self, timeout_ms: int = 4000):
        """Find the frame/page that contains the iLPNs UI (poll until timeout)."""

        def _match(frames):
            for frame in frames:
                try:
                    url = frame.url or ""
                except Exception:
                    url = ""
                if "LPNListInbound" in url or "lpnlistinbound" in url.lower() or "/lpn" in url.lower():
                    return frame
            return None

        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            frame = _match(self.page.frames)
            if frame:
                return frame

            try:
                # Try explicit iframe lookup by src/name in current page
                iframe = self.page.locator(
                    "iframe[src*='LPNListInbound'], iframe[src*='/lpn'], iframe[name*='LPN'], iframe[id*='LPN']"
                ).first
                if iframe.count() > 0:
                    cf = iframe.content_frame()
                    if cf and ("lpn" in (cf.url or "").lower() or "lpnlistinbound" in (cf.url or "").lower()):
                        return cf
            except Exception:
                pass

            try:
                # Try iframe inside a visible window (better for ExtJS windows)
                win_iframe = (
                    self.page.locator("div.x-window:visible iframe").first
                )
                if win_iframe.count() > 0:
                    cf = win_iframe.content_frame()
                    if cf and ("lpn" in (cf.url or "").lower() or "lpnlistinbound" in (cf.url or "").lower()):
                        return cf
            except Exception:
                pass

            try:
                for p in self.page.context.pages:
                    frame = _match(p.frames)
                    if frame:
                        return frame
            except Exception:
                pass

            self.page.wait_for_timeout(150)

        return None

    def _wait_for_ilpn_apply(self, timeout_ms: int, operation_note: str, entry: dict, default_screenshot: str | None):
        """Wait for iLPN apply to finish (mask cleared) then capture before close."""
        frame = self._find_ilpn_frame(timeout_ms=2000)
        prev_snapshot = None
        if frame:
            try:
                prev_snapshot = HashUtils.get_frame_snapshot(frame)
            except Exception:
                prev_snapshot = None

        if frame and prev_snapshot:
            WaitUtils.wait_for_screen_change(
                lambda: self._find_ilpn_frame(timeout_ms=500),
                prev_snapshot,
                timeout_ms=timeout_ms,
                interval_ms=250,
                warn_on_timeout=True,
            )
        else:
            # Fallback: wait for masks or timeout
            deadline = time.time() + timeout_ms / 1000
            try:
                mask = self.page.locator("div.x-mask:visible")
            except Exception:
                mask = None

            if mask is None:
                self.page.wait_for_timeout(timeout_ms)
            else:
                while time.time() < deadline:
                    try:
                        if mask.count() == 0:
                            break
                    except Exception:
                        break
                    self.page.wait_for_timeout(150)

        # Small settle delay
        self.page.wait_for_timeout(300)

        tag = entry.get("post_screenshot_tag") or default_screenshot
        if tag:
            self.screenshot_mgr.capture(self.page, tag, f"{operation_note} (after fill)")

    # =========================================================================
    # HELPERS - Screenshots
    # =========================================================================

    def _capture_success(self, asn: str, item: str, qty: int):
        """Capture success screenshot."""
        unit = "Unit" if qty == 1 else "Units"
        self.screenshot_mgr.capture_rf_window(
            self.page, "receive_complete",
            f"ASN {asn}: {qty} {unit} of {item}"
        )

    def _capture_deviation(self, flow: str, auto_handle: bool):
        """Capture deviation screenshot."""
        self.screenshot_mgr.capture_rf_window(
            self.page, f"deviation_{flow.lower()}",
            f"Flow: {flow} (auto_handle={auto_handle})"
        )
