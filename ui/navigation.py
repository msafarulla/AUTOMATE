import time
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError
from core.screenshot import ScreenshotManager
from utils.hash_utils import HashUtils
from utils.wait_utils import WaitUtils
from utils.eval_utils import safe_page_evaluate
from core.logger import app_log


class NavigationManager:
    def __init__(self, page: Page, screenshot_mgr: ScreenshotManager):
        self.page = page
        self.screenshot_mgr = screenshot_mgr
        self._ensure_menu_overlay_closed_after_sign_on = False

    def change_warehouse(self, warehouse: str):
        """Select facility and warehouse only if different"""
        page = self.page

        # Locate the warehouse/facility dropdown element
        current_warehouse_el = page.locator(":text-matches('- SOA')").first

        # Get the currently displayed warehouse/facility text
        current_warehouse = current_warehouse_el.inner_text().strip()
        app_log(f"🏢 Current warehouse: {current_warehouse}")

        # If it already matches, skip changing
        if warehouse.lower() in current_warehouse.lower():
            app_log(f"✅ Already in desired warehouse: {current_warehouse}")
            return

        # Otherwise, open dropdown and change warehouse
        current_warehouse_el.click()

        warehouse_input = page.locator("input[type='text']:visible").first
        warehouse_input.click()
        page.wait_for_selector("ul.x-list-plain li", timeout=2000)

        # Select the desired warehouse
        page.locator(f"ul.x-list-plain li:has-text('{warehouse}')").click()

        # Wait for the screen to reload
        prev_snapshot = HashUtils.get_frame_snapshot(page.main_frame)
        page.get_by_text("Apply", exact=True).click()
        WaitUtils.wait_for_screen_change(lambda: page.main_frame, prev_snapshot)

        # Capture screenshot and confirm
        self.screenshot_mgr.capture(page, f"warehouse_{warehouse}",
                                    f"Changed to {warehouse}")
        app_log(f"✅ Changed warehouse to {warehouse}")

    def open_menu_item(self, search_term: str, match_text: str, max_attempt: int = 10) -> bool:
        import re
        from difflib import ndiff

        def normalize_text(s: str) -> str:
            # Normalize invisible chars, spacing, and case
            return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip().lower()

        page = self.page
        normalized_match = normalize_text(match_text)

        for attempt in range(max_attempt):
            self.close_active_windows()
            page.wait_for_timeout(500)

            self._open_menu_panel()
            self._reset_menu_filter()

            search_box = page.locator("div.x-window input[type='text']")
            search_box.wait_for(timeout=2000)
            try:
                search_box.fill("")
            except Exception:
                pass
            search_box.fill(search_term)
            page.wait_for_timeout(300)

            items = page.locator("ul.x-list-plain:visible li.x-boundlist-item")
            count = self._wait_for_menu_results(items)
            app_log(f"🔍 Found {count} items for '{search_term}' (attempt {attempt + 1})")

            if count == 0:
                app_log("⚠️ Menu returned no items; retrying.")
                continue

            retry_due_to_click_failure = False

            for i in range(count):
                text = items.nth(i).inner_text().strip()
                normalized_text = normalize_text(text)
                app_log(f"Option {i + 1}: RAW: {repr(text)}")

                if normalized_text == normalized_match:
                    self.screenshot_mgr.capture(page, f"Selecting {normalized_text} UI", f"Selecting {text} UI")
                    app_log(f"✅ Exact match found: '{text}' — selecting it")
                    try:
                        self._activate_menu_selection(items.nth(i), "rf menu" in normalized_match)
                    except PlaywrightTimeoutError:
                        app_log("⚠️ Menu list went stale before click; retrying search.")
                        retry_due_to_click_failure = True
                        break

                    self._maybe_maximize_rf_window(normalized_match)
                    self._maybe_center_post_message_window(normalized_match)
                    self._maybe_maximize_workspace_window(normalized_match)
                    page.wait_for_timeout(500)
                    return True
                else:
                    diff = ''.join(ndiff([normalized_text], [normalized_match]))
                    app_log(f"🟡 No match for Option {i + 1}. Diff:\n{diff}")

            if retry_due_to_click_failure:
                continue

            app_log("⚠️ No exact match in this attempt; retrying.")

        app_log(f"❌ No exact match found for: '{match_text}' after retries")
        return False

    def _open_menu_panel(self):
        """Open the navigation panel (idempotent)."""
        page = self.page
        try:
            panel = page.locator("div[id^='mps_menu']:visible")
            if panel.count() > 0:
                return
        except Exception:
            pass
        self._wait_for_mask_to_clear()
        page.locator("a.x-btn").first.click()
        self._wait_for_mask_to_clear(timeout_ms=2000)

    def _wait_for_mask_to_clear(self, timeout_ms: int = 4000, poll_ms: int = 150):
        """Pause while ExtJS masks intercept pointer events."""
        page = self.page
        mask = page.locator("div.x-mask:visible")
        deadline = time.time() + (timeout_ms / 1000)
        notified = False
        while True:
            try:
                if mask.count() == 0:
                    return
            except Exception:
                return

            if not notified:
                app_log("⏳ Waiting for blocking mask to clear...")
                notified = True

            if time.time() >= deadline:
                app_log("⚠️ Mask still present; continuing anyway.")
                return

            page.wait_for_timeout(poll_ms)

    def _wait_for_menu_results(self, items_locator, retries: int = 10, delay_ms: int = 200) -> int:
        """Poll for menu search results so slow loads don't return zero prematurely."""
        for _ in range(retries):
            count = items_locator.count()
            if count > 0:
                return count
            self.page.wait_for_timeout(delay_ms)
        return items_locator.count()

    def close_active_windows(self, skip_titles=None):
        """Close any open workspace windows so new screens start fresh."""
        skip = {title.strip().lower() for title in (skip_titles or [])}
        while True:
            window = self._find_workspace_window(skip)
            if window is None:
                break
            title = self._get_window_title(window)
            app_log(f"🧹 Closing window: {title or 'Unnamed window'}")
            if not self._close_window(window):
                break
            self.page.wait_for_timeout(200)

    def _find_workspace_window(self, skip_titles):
        windows = self.page.locator("div.x-window:visible")
        count = windows.count()
        for idx in range(count):
            window = windows.nth(idx)
            if self._should_skip_window(window, skip_titles):
                continue
            return window
        return None

    def _should_skip_window(self, window: Locator, skip_titles) -> bool:
        try:
            win_id = window.get_attribute("id") or ""
            if win_id.startswith("mps_menu"):
                return True
        except Exception:
            pass

        title = self._get_window_title(window)
        if not title:
            return False
        normalized = title.lower()
        if normalized == "menu":
            return True
        return normalized in skip_titles

    def _get_window_title(self, window: Locator) -> str:
        try:
            return window.locator(".x-title-text").first.inner_text().strip()
        except Exception:
            return ""

    def _close_window(self, window: Locator) -> bool:
        for locator in (
            ".x-tool-close",
            "a.x-btn:has-text('Close')",
            "button:has-text('Close')",
        ):
            try:
                window.locator(locator).first.click()
                window.wait_for(state="hidden", timeout=2000)
                return True
            except Exception:
                continue
        try:
            self.page.keyboard.press("Escape")
            window.wait_for(state="hidden", timeout=1500)
            return True
        except Exception:
            return False

    def _reset_menu_filter(self):
        """Click the Show All button to reset menu filtering if present."""
        page = self.page
        button = page.locator("div.x-window:visible a.x-btn:has-text('Show All')")
        try:
            button.wait_for(state="visible", timeout=500)
            button.click()
            page.wait_for_timeout(200)
        except Exception:
            pass

    def _ensure_menu_closed(self):
        """Make sure the menu overlay is not blocking the workspace."""
        page = self.page
        panel = page.locator("div[id^='mps_menu']:visible")
        try:
            if panel.count() == 0:
                return
        except Exception:
            return

        try:
            panel.first.wait_for(state="hidden", timeout=1500)
            return
        except Exception:
            pass

        try:
            panel.locator(".x-tool-close").first.click()
        except Exception:
            pass

        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        try:
            panel.first.wait_for(state="hidden", timeout=1000)
        except Exception:
            page.wait_for_timeout(500)

    def close_menu_overlay_after_sign_on(self):
        if not self._ensure_menu_overlay_closed_after_sign_on:
            return
        self._ensure_menu_closed()
        self._ensure_menu_overlay_closed_after_sign_on = False

    def _maybe_maximize_rf_window(self, normalized_match: str):
        """Maximize RF window immediately after launching RF menu."""
        if "rf menu" not in normalized_match:
            return

        try:
            self.page.locator("div.x-window:has-text('RF Menu')").first.wait_for(
                state="visible", timeout=4000
            )
        except Exception:
            pass

        try:
            success = safe_page_evaluate(
                self.page,
                """
            () => {
                const win = Ext.ComponentQuery.query('window[title~="RF"]')[0];
                if (!win) return false;
                const topPadding = Math.max(window.innerHeight * 0.05, 15);
                const leftPadding = Math.max(window.innerWidth * 0.01, 12);
                win.setHeight(window.innerHeight * 0.9);
                win.setX(leftPadding);
                win.setY(topPadding);
                win.updateLayout();
                return true;
            }
                """,
                description="NavigationManager._maybe_maximize_rf_window",
            )
            if success:
                app_log("🪟 RF window maximized from navigation.")
        except Exception as e:
            app_log(f"⚠️ Unable to maximize RF window: {e}")

    def _maybe_center_post_message_window(self, normalized_match: str):
        """Pin the Post Message window near the top-center so it does not cascade down."""
        if "post message" not in normalized_match:
            return

        for attempt in range(8):
            success = self._reposition_ext_window(
                selector='window[title*="Post Message"]',
                offset_top_ratio=0.05,
                fallback_width=640,
                label="Post Message",
            )
            if success:
                if attempt:
                    app_log(f"🪟 Post Message window centered after retry {attempt + 1}.")
                else:
                    app_log("🪟 Post Message window centered near top.")
                return
            self.page.wait_for_timeout(200)
        app_log("⚠️ Post Message window never appeared for centering.")

    def _maybe_maximize_workspace_window(self, normalized_match: str):
        """Maximize non-RF workspace windows so screenshots capture more detail."""
        if "rf menu" in normalized_match:
            return

        for attempt in range(6):
            if self._maximize_active_non_rf_window():
                if attempt:
                    app_log(f"🪟 Workspace window maximized after retry {attempt + 1}.")
                else:
                    app_log("🪟 Workspace window maximized for capture.")
                return
            self.page.wait_for_timeout(200)

    def _activate_menu_selection(self, item_locator: Locator, use_info_button: bool):
        """
        Select the menu entry, preferring the blue info button when requested since
        some RF-focused menu items only launch via that icon.
        """
        if use_info_button and self._click_info_icon(item_locator):
            return

        item_locator.click()

    def _click_info_icon(self, item_locator: Locator) -> bool:
        """Try multiple selectors to hit the blue info button within a menu row."""
        selectors = [
            "button:has-text('i')",
            "a:has-text('i')",
            "[class*='info']",
            "[data-qtip*='Quick Menu']",
            "[data-qtip*='Info']",
        ]

        for sel in selectors:
            candidate = item_locator.locator(sel).first
            try:
                candidate.wait_for(state="visible", timeout=200)
                candidate.click()
                return True
            except Exception:
                continue

        # Fallback: click near the right edge where the icon normally sits.
        try:
            box = item_locator.bounding_box()
            if not box:
                return False
            x = box["x"] + box["width"] - 8
            y = box["y"] + (box["height"] / 2)
            self.page.mouse.click(x, y)
            return True
        except Exception:
            return False

    def _reposition_ext_window(
        self,
        *,
        selector: str,
        offset_top_ratio: float = 0.08,
        fallback_width: float = 600,
        fallback_height: float = 480,
        label: str = "Ext window",
    ) -> bool:
        """Utility to move ExtJS windows to a predictable place."""
        try:
            return bool(
                safe_page_evaluate(
                    self.page,
                    """
                (params) => {
                    if (!window.Ext || !Ext.ComponentQuery) {
                        return false;
                    }
                    const wins = Ext.ComponentQuery.query(params.selector) || [];
                    if (!wins.length) {
                        return false;
                    }
                    const win = wins[wins.length - 1];
                    const width =
                        (win.getWidth && win.getWidth()) ||
                        (win.el && win.el.getWidth && win.el.getWidth()) ||
                        params.fallbackWidth;
                    const height =
                        (win.getHeight && win.getHeight()) ||
                        (win.el && win.el.getHeight && win.el.getHeight()) ||
                        params.fallbackHeight;
                    const topRatio = Math.max(0, Math.min(0.4, params.offsetTopRatio));
                    const x = Math.max(12, (window.innerWidth - width) / 2);
                    const y = Math.max(12, window.innerHeight * topRatio);
                    if (win.setPosition) {
                        win.setPosition(x, y);
                    } else if (win.setXY) {
                        win.setXY([x, y]);
                    } else {
                        win.center?.();
                        win.setY?.(y);
                    }
                    if (win.setHeight && height) {
                        const maxHeight = window.innerHeight - 24;
                        win.setHeight(Math.min(maxHeight, Math.max(200, height)));
                    }
                    win.toFront?.();
                    win.updateLayout?.();
                    return true;
                }
                    """,
                    {
                        "selector": selector,
                        "offsetTopRatio": float(offset_top_ratio),
                        "fallbackWidth": float(fallback_width),
                        "fallbackHeight": float(fallback_height),
                        "label": label,
                    },
                    description=f"NavigationManager._reposition_ext_window[{label}]",
                )
            )
        except Exception as exc:
            app_log(f"⚠️ Unable to reposition {label}: {exc}")
            return False

    def _maximize_active_non_rf_window(self) -> bool:
        """Use Ext WindowManager to resize the active workspace window (excluding RF)."""
        try:
            return bool(
                safe_page_evaluate(
                    self.page,
                    """
                () => {
                    if (!window.Ext || !Ext.WindowManager || !Ext.WindowManager.getActive) {
                        return false;
                    }
                    const win = Ext.WindowManager.getActive();
                    if (!win) {
                        return false;
                    }
                    const title = ((win.title || win.titleText || '') + '').toLowerCase();
                    if (!title || title.includes('rf menu') || title === 'rf') {
                        return false;
                    }
                    const viewportWidth = window.innerWidth;
                    const viewportHeight = window.innerHeight;
                    const width = Math.max(400, viewportWidth * 0.92);
                    const height = Math.max(300, viewportHeight * 0.9);
                    const x = Math.max(8, (viewportWidth - width) / 2);
                    const y = Math.max(8, viewportHeight * 0.04);
                    if (win.setSize) {
                        win.setSize(width, height);
                    } else {
                        win.setWidth?.(width);
                        win.setHeight?.(height);
                    }
                    if (win.setPosition) {
                        win.setPosition(x, y);
                    } else if (win.center) {
                        win.center();
                    }
                    win.updateLayout?.();
                    win.toFront?.();
                    return true;
                }
                    """,
                    description="NavigationManager._maximize_active_non_rf_window",
                )
            )
        except Exception as exc:
            app_log(f"⚠️ Unable to maximize workspace window: {exc}")
            return False
