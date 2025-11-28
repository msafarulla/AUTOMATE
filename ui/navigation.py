"""
Navigation Manager - Handles WMS menu navigation and window management.

Responsibilities:
- Change warehouse/facility
- Open menu items by search
- Manage ExtJS windows (close, focus, resize)
"""
import re
import time
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeout

from core.screenshot import ScreenshotManager
from core.logger import app_log
from utils.wait_utils import WaitUtils
from utils.hash_utils import HashUtils
from utils.eval_utils import safe_page_evaluate


class NavigationManager:
    """Handles WMS navigation and window management."""

    def __init__(self, page: Page, screenshot_mgr: ScreenshotManager):
        self.page = page
        self.screenshot_mgr = screenshot_mgr

    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================

    def change_warehouse(self, warehouse: str, onDemand: bool = True):
        """Change to specified warehouse if not already selected."""
        current_el = self.page.locator(":text-matches('- SOA')").first
        current = current_el.inner_text().strip()
        app_log(f"🏢 Current warehouse: {current}")

        if warehouse.lower() in current.lower():
            app_log(f"✅ Already in {warehouse}")
            return

        # Open dropdown and select
        current_el.click()
        self.page.locator("input[type='text']:visible").first.click()
        self.page.wait_for_selector("ul.x-list-plain li", timeout=2000)
        self.page.locator(f"ul.x-list-plain li:has-text('{warehouse}')").click()

        # Apply and wait
        prev = HashUtils.get_frame_snapshot(self.page.main_frame)
        self.page.get_by_text("Apply", exact=True).click()
        WaitUtils.wait_for_screen_change(lambda: self.page.main_frame, prev, warn_on_timeout=False)

        self.screenshot_mgr.capture(self.page, f"warehouse_{warehouse}", f"Changed to {warehouse}", onDemand)
        app_log(f"✅ Changed to {warehouse}")

    def open_menu_item(
        self,
        search_term: str,
        match_text: str,
        onDemand: bool = True,
    ) -> bool:
        """Open a menu item by searching and selecting exact match."""
        normalized_match = self._normalize(match_text)

        try:
            # Keep the current RF window alive so mid-flow prompts (e.g., post-qty info) remain active.
            self.close_active_windows(
                skip_titles=[match_text, "rf", "rf menu", "rf menu (distribution)"]
            )
        except Exception:
            pass

        self._open_menu_panel()
        self._reset_menu_filter()
        self._do_search(search_term)

        # Find and click match
        items = self.page.locator("ul.x-list-plain:visible li.x-boundlist-item")
        count = self._wait_for_results(items)
        app_log(f"🔍 Found {count} items for '{search_term}'")

        if count == 0:
            app_log("⚠️ No results found for search term.")
            return False

        # Look for exact match
        for i in range(count):
            item = items.nth(i)
            text = self._normalize(item.inner_text().strip())

            if text == normalized_match:
                app_log(f"✅ Match found: '{match_text}'")
                self.screenshot_mgr.capture(self.page, f"select_{text}", f"Selecting {match_text}", onDemand)

                try:
                    self._click_menu_item(item, "rf menu" in normalized_match)
                except PlaywrightTimeout:
                    app_log("⚠️ Menu went stale while clicking match.")
                    return False
                self._post_selection_adjustments(normalized_match)
                WaitUtils.wait_brief(self.page)
                try:
                    if "rf menu" in normalized_match:
                        self.maximize_rf_window()
                    else:
                        self.maximize_non_rf_windows()
                except Exception:
                    pass
                return True

        app_log(f"⚠️ No exact match found for '{match_text}'")
        app_log(f"❌ Could not find: '{match_text}'")
        return False

    def focus_window_by_title(self, title: str) -> bool:
        """Bring window with matching title to front."""
        for window in self._get_visible_windows():
            win_title = self._get_title(window)
            if win_title and title.lower() in win_title.lower():
                app_log(f"✨ Focusing: {win_title}")
                window.evaluate("el => el.style.zIndex = '99999999'")
                return True
        app_log(f"⚠️ Window not found: {title}")
        return False

    def close_active_windows(self, skip_titles: list[str] = None):
        """Close all workspace windows except those in skip list."""
        skip = {t.lower() for t in (skip_titles or []) if t}

        while True:
            window = self._find_closeable_window(skip)
            if not window:
                break
            title = self._get_title(window) or "Unnamed"
            app_log(f"🧹 Closing: {title}")
            if not self._close_window(window):
                break
            WaitUtils.wait_brief(self.page)

    def close_menu_overlay_after_sign_on(self):
        """Close menu overlay if open after login."""
        panel = self.page.locator("div[id^='mps_menu']:visible")
        try:
            if panel.count() == 0:
                return
            panel.locator(".x-tool-close").first.click()
        except Exception:
            pass

    # =========================================================================
    # MENU HELPERS
    # =========================================================================

    def _open_menu_panel(self):
        """Open the navigation panel."""
        try:
            if self.page.locator("div[id^='mps_menu']:visible").count() > 0:
                return
        except Exception:
            pass
        
        self._wait_for_mask()
        self.page.locator("a.x-btn").first.click()
        self._wait_for_mask(2000)

    def _reset_menu_filter(self):
        """Click Show All button if present."""
        btn = self.page.locator("div.x-window:visible a.x-btn:has-text('Show All')")
        try:
            btn.wait_for(state="visible", timeout=500)
            btn.click()
            WaitUtils.wait_brief(self.page)
        except Exception:
            pass

    def _do_search(self, term: str):
        """Type search term in menu."""
        search_box = self.page.locator("div.x-window input[type='text']")
        search_box.wait_for(timeout=2000)
        try:
            search_box.fill("")
        except Exception:
            pass
        search_box.fill(term)
        WaitUtils.wait_brief(self.page)

    def _wait_for_results(self, locator: Locator, retries: int = 10) -> int:
        """Wait for menu search results to populate."""
        for _ in range(retries):
            count = locator.count()
            if count > 0:
                return count
            WaitUtils.wait_brief(self.page)
        return locator.count()

    def _click_menu_item(self, item: Locator, use_info_button: bool):
        """Click menu item, optionally via info button."""
        if use_info_button:
            # Try clicking info icon on right side
            try:
                box = item.bounding_box()
                if box:
                    self.page.mouse.click(box["x"] + box["width"] - 8, box["y"] + box["height"] / 2)
                    return
            except Exception:
                pass
        item.click()

    def _post_selection_adjustments(self, match: str):
        """Adjust window position/size after selection (maximize non-RF windows)."""
        if "rf menu" in match:
            return

        # Center specific windows first if needed, then maximize for more visibility.
        if "post message" in match:
            self._center_window('window[title*="Post Message"]', "Post Message")
        self._maximize_non_rf_windows()

    # =========================================================================
    # WINDOW HELPERS
    # =========================================================================

    def _get_visible_windows(self) -> list[Locator]:
        """Get all visible ExtJS windows."""
        windows = self.page.locator("div.x-window:visible")
        return [windows.nth(i) for i in range(windows.count())]

    def _find_closeable_window(self, skip_titles: set) -> Locator | None:
        """Find a window that can be closed."""
        for window in self._get_visible_windows():
            # Skip menu panel
            try:
                win_id = window.get_attribute("id") or ""
                if win_id.startswith("mps_menu"):
                    continue
            except Exception:
                pass

            title = (self._get_title(window) or "").lower()
            if any(skip in title for skip in skip_titles):
                continue
            return window
        return None

    def _get_title(self, window: Locator) -> str:
        """Get window title."""
        try:
            return window.locator(".x-title-text").first.inner_text().strip()
        except Exception:
            return ""

    def _close_window(self, window: Locator) -> bool:
        """Close a window using various methods."""
        # Try close button
        for selector in (".x-tool-close", "a.x-btn:has-text('Close')", "button:has-text('Close')"):
            try:
                window.locator(selector).first.click()
                window.wait_for(state="hidden", timeout=2000)
                return True
            except Exception:
                continue

        # Try escape key
        try:
            self.page.keyboard.press("Escape")
            window.wait_for(state="hidden", timeout=1500)
            return True
        except Exception:
            return False

    def _wait_for_mask(self, timeout_ms: int = 4000):
        """Wait for ExtJS loading mask to clear."""
        if WaitUtils.wait_for_mask_clear(self.page, timeout_ms=timeout_ms):
            return
        # Fallback to a short pause if mask check failed (e.g., page detached).
        try:
            WaitUtils.wait_brief(self.page)
        except Exception:
            pass

    # =========================================================================
    # EXTJS WINDOW MANIPULATION
    # =========================================================================

    def _center_window(self, selector: str, label: str):
        """Center an ExtJS window near top of viewport."""
        for _ in range(8):
            success = safe_page_evaluate(self.page, """
                (params) => {
                    if (!window.Ext?.ComponentQuery) return false;
                    const wins = Ext.ComponentQuery.query(params.selector);
                    if (!wins.length) return false;
                    
                    const win = wins[wins.length - 1];
                    const w = win.getWidth?.() || 600;
                    const x = Math.max(12, (window.innerWidth - w) / 2);
                    const y = Math.max(12, window.innerHeight * 0.05);
                    
                    win.setPosition?.(x, y);
                    win.toFront?.();
                    return true;
                }
            """, {"selector": selector}, description=f"center_{label}")
            
            if success:
                app_log(f"🪟 Centered {label}")
                return
            WaitUtils.wait_brief(self.page)

    def _maximize_active_window(self):
        """Maximize the active non-RF window."""
        safe_page_evaluate(self.page, """
            () => {
                if (!window.Ext?.WindowManager?.getActive) return false;
                const win = Ext.WindowManager.getActive();
                if (!win) return false;
                
                const title = (win.title || '').toLowerCase();
                if (title.includes('rf menu') || title === 'rf') return false;
                
                const w = Math.max(400, window.innerWidth * 0.92);
                const h = Math.max(300, window.innerHeight * 0.9);
                const x = Math.max(8, (window.innerWidth - w) / 2);
                const y = Math.max(8, window.innerHeight * 0.04);
                
                win.setSize?.(w, h);
                win.setPosition?.(x, y);
                win.toFront?.();
                return true;
            }
        """, description="maximize_window")

    def _maximize_non_rf_windows(self):
        """Maximize all visible non-RF windows for better capture."""
        # First, try the native maximize buttons on visible windows (if present).
        clicked = 0
        try:
            windows = self.page.locator("div.x-window:visible")
            count = windows.count()
            for i in range(count):
                win = windows.nth(i)
                try:
                    title = (win.locator(".x-window-header-text").inner_text(timeout=300) or "").lower()
                    if "rf menu" in title or title == "rf":
                        continue
                except Exception:
                    title = ""
                try:
                    btn = win.locator(".x-tool-maximize:visible").first
                    if btn.count() > 0:
                        btn.click(timeout=800)
                        clicked += 1
                        continue
                except Exception:
                    pass
        except Exception:
            pass

        ext_resized = safe_page_evaluate(self.page, """
            () => {
                if (!window.Ext?.WindowManager?.getAll) return 0;
                const wins = Ext.WindowManager.getAll().items || [];
                let changed = 0;
                wins.forEach(win => {
                    const title = (win.title || '').toLowerCase();
                    if (title.includes('rf menu') || title === 'rf') return;
                    try {
                        if (typeof win.maximize === 'function') {
                            win.maximize();
                        } else {
                            const w = Math.max(400, window.innerWidth * 0.95);
                            const h = Math.max(300, window.innerHeight * 0.95);
                            const x = Math.max(4, (window.innerWidth - w) / 2);
                            const y = Math.max(4, window.innerHeight * 0.03);
                            win.setSize?.(w, h);
                            win.setPosition?.(x, y);
                            win.setPagePosition?.(x, y);
                        }
                        win.toFront?.();
                        win.updateLayout?.();
                        changed += 1;
                    } catch (e) {}
                });
                return changed;
            }
        """, description="maximize_non_rf_windows")

        resized = clicked + (ext_resized or 0)

        # Fallback: some windows may not be registered with WindowManager; size them via ComponentQuery.
        if resized == 0:
            fallback_resized = safe_page_evaluate(self.page, """
                () => {
                    if (!window.Ext?.ComponentQuery) return 0;
                    const wins = Ext.ComponentQuery.query('window');
                    let changed = 0;
                    wins.forEach(win => {
                        const title = (win.title || '').toLowerCase();
                        if (title.includes('rf menu') || title === 'rf') return;
                        try {
                            const w = Math.max(400, window.innerWidth * 0.95);
                            const h = Math.max(300, window.innerHeight * 0.95);
                            const x = Math.max(4, (window.innerWidth - w) / 2);
                            const y = Math.max(4, window.innerHeight * 0.03);
                            win.setSize?.(w, h);
                            win.setPosition?.(x, y);
                            win.setPagePosition?.(x, y);
                            win.toFront?.();
                            win.updateLayout?.();
                            changed += 1;
                        } catch (e) {}
                    });
                    return changed;
                }
            """, description="maximize_non_rf_windows_fallback")
            resized = fallback_resized or 0

        if resized:
            app_log(f"🪟 Maximized {resized} non-RF window(s)")
        else:
            app_log("ℹ️ No non-RF windows maximized (none found or already excluded)")

    def maximize_rf_window(self):
        """Ensure the RF Menu window uses most of the viewport height and aligns with non-RF origin."""
        try:
            rf_window = self.page.locator("div.x-window:has-text('RF Menu')").last
            rf_window.wait_for(state="visible", timeout=3000)
        except Exception:
            return False

        try:
            rf_window.evaluate("""
                (el) => {
                    const vw = window.innerWidth || document.documentElement?.clientWidth || 1366;
                    const vh = window.innerHeight || document.documentElement?.clientHeight || 900;
                    const rect = el.getBoundingClientRect();
                    const width = rect?.width || Math.max(360, vw * 0.4);
                    const target = Math.max(600, vh - 40);
                    const x = Math.max(4, rect?.left || 4);
                    const y = Math.max(4, vh * 0.03);
                    el.style.setProperty("height", `${target}px`, "important");
                    el.style.setProperty("min-height", `${target}px`, "important");
                    el.style.setProperty("top", `${y}px`, "important");
                    el.style.setProperty("left", `${x}px`, "important");
                    el.style.setProperty("right", "auto", "important");
                }
            """)
            return True
        except Exception:
            return False

    def maximize_non_rf_windows(self):
        """Public wrapper to maximize non-RF windows."""
        return self._maximize_non_rf_windows()

    # =========================================================================
    # UTILITIES
    # =========================================================================

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for comparison."""
        return re.sub(r'\s+', ' ', text.replace('\xa0', ' ')).strip().lower()
