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
from utils.hash_utils import HashUtils
from utils.wait_utils import WaitUtils
from utils.eval_utils import safe_page_evaluate


class NavigationManager:
    """Handles WMS navigation and window management."""

    def __init__(self, page: Page, screenshot_mgr: ScreenshotManager):
        self.page = page
        self.screenshot_mgr = screenshot_mgr

    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================

    def change_warehouse(self, warehouse: str):
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
        WaitUtils.wait_for_screen_change(lambda: self.page.main_frame, prev)

        self.screenshot_mgr.capture(self.page, f"warehouse_{warehouse}", f"Changed to {warehouse}")
        app_log(f"✅ Changed to {warehouse}")

    def open_menu_item(self, search_term: str, match_text: str, 
                       max_attempts: int = 1, close_existing: bool = True) -> bool:
        """Open a menu item by searching and selecting exact match."""
        normalized_match = self._normalize(match_text)

        for attempt in range(max_attempts):
            if close_existing:
                self.close_active_windows()
            self.page.wait_for_timeout(500)

            # Open menu and search
            self._open_menu_panel()
            self._reset_menu_filter()
            self._do_search(search_term)

            # Find and click match
            items = self.page.locator("ul.x-list-plain:visible li.x-boundlist-item")
            count = self._wait_for_results(items)
            app_log(f"🔍 Found {count} items for '{search_term}' (attempt {attempt + 1})")

            if count == 0:
                continue

            # Look for exact match
            for i in range(count):
                item = items.nth(i)
                text = self._normalize(item.inner_text().strip())
                
                if text == normalized_match:
                    app_log(f"✅ Match found: '{match_text}'")
                    self.screenshot_mgr.capture(self.page, f"select_{text}", f"Selecting {match_text}")
                    
                    try:
                        self._click_menu_item(item, "rf menu" in normalized_match)
                    except PlaywrightTimeout:
                        app_log("⚠️ Menu went stale, retrying...")
                        break

                    self._post_selection_adjustments(normalized_match)
                    self.page.wait_for_timeout(3000)
                    return True

            app_log("⚠️ No exact match found, retrying...")

        app_log(f"❌ Could not find: '{match_text}'")
        return False

    def open_tasks_ui(self, search: str = "tasks", match: str = "Tasks (Configuration)",
                      close_existing: bool = True) -> bool:
        """Open Tasks UI."""
        if self.open_menu_item(search, match, close_existing=close_existing):
            self.screenshot_mgr.capture(self.page, "tasks_ui", "Tasks UI")
            return True
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
        skip.add("menu")  # Never close main menu

        while True:
            window = self._find_closeable_window(skip)
            if not window:
                break
            title = self._get_title(window) or "Unnamed"
            app_log(f"🧹 Closing: {title}")
            if not self._close_window(window):
                break
            self.page.wait_for_timeout(200)

    def close_menu_overlay_after_sign_on(self):
        """Close menu overlay if open after login."""
        panel = self.page.locator("div[id^='mps_menu']:visible")
        try:
            if panel.count() == 0:
                return
            panel.locator(".x-tool-close").first.click()
        except Exception:
            pass

    def enable_context_menu(self):
        """Allow right-click/inspect by disabling app-level contextmenu blockers."""
        safe_page_evaluate(self.page, """
            () => {
                const allowContext = () => {
                    const unblock = (ev) => {
                        ev.stopPropagation();
                        // Do not preventDefault so the browser menu shows.
                    };
                    document.addEventListener('contextmenu', unblock, true);
                    window.addEventListener('contextmenu', unblock, true);
                    document.querySelectorAll('[oncontextmenu]').forEach(el => {
                        el.oncontextmenu = null;
                    });
                };
                allowContext();
                // Re-apply after a short delay in case framework rebinds handlers.
                setTimeout(allowContext, 1000);
            }
        """, description="enable_context_menu")

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
            self.page.wait_for_timeout(200)
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
        self.page.wait_for_timeout(300)

    def _wait_for_results(self, locator: Locator, retries: int = 10) -> int:
        """Wait for menu search results to populate."""
        for _ in range(retries):
            count = locator.count()
            if count > 0:
                return count
            self.page.wait_for_timeout(200)
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
        mask = self.page.locator("div.x-mask:visible")
        deadline = time.time() + timeout_ms / 1000
        
        while time.time() < deadline:
            try:
                if mask.count() == 0:
                    return
            except Exception:
                return
            self.page.wait_for_timeout(150)

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
            self.page.wait_for_timeout(200)

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
        resized = safe_page_evaluate(
            self.page,
            """
            () => {
                const ext = window.Ext;
                if (!ext?.WindowManager?.getAll) return 0;
                const wins = ext.WindowManager.getAll().items || [];
                const w = Math.max(480, window.innerWidth * 0.95);
                const h = Math.max(360, window.innerHeight * 0.95);
                const x = Math.max(6, (window.innerWidth - w) / 2);
                const y = Math.max(6, window.innerHeight * 0.03);
                let changed = 0;
                wins.forEach(win => {
                    const title = (win.title || '').toLowerCase();
                    if (title.includes('rf menu') || title === 'rf') return;
                    try {
                        win.setSize?.(w, h);
                        win.setPosition?.(x, y);
                        win.setPagePosition?.(x, y);
                        win.setMinWidth?.(w);
                        win.setMinHeight?.(h);
                        win.updateLayout?.();
                        win.toFront?.();
                        changed += 1;
                    } catch (e) {}
                });
                return changed;
            }
            """,
            description="maximize_non_rf_windows",
        )

        if resized:
            app_log(f"🪟 Maximized {resized} non-RF window(s)")
        else:
            app_log("ℹ️ No non-RF windows maximized (none found or already excluded)")

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
