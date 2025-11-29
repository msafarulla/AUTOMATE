"""
Shared helper to drive the iLPN quick filter from both receive flow and debug CLI.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING

from config.settings import Settings
from core.logger import app_log, rf_log
from core.screenshot import ScreenshotManager
from utils.wait_utils import WaitUtils

from .ilpn_js_scripts import (
    DOM_OPEN_ILPN_ROW_SCRIPT,
    EXT_OPEN_FIRST_ROW_SCRIPT,
    EXT_STORE_COUNT_SCRIPT,
    HIDDEN_INPUT_FILL_SCRIPT,
    TAB_CLICK_SCRIPT,
    TAB_DIAGNOSTIC_SCRIPT,
)

if TYPE_CHECKING:
    from typing import Any


@dataclass
class TabClickConfig:
    """Configuration for tab clicking operations."""
    screenshot_mgr: ScreenshotManager | None = None
    screenshot_tag: str = "ilpn_tab"
    operation_note: str | None = None
    click_timeout_ms: int = 3000
    capture_after_tabs: bool = True


class FrameFinder:
    """Locates the appropriate frame for iLPN operations."""
    
    @staticmethod
    def find_ilpn_frame(page) -> Any | None:
        """Locate the frame that hosts the iLPNs grid."""
        app_log("🔍 Scanning frames for iLPN content...")

        def score(frame) -> tuple[int, int]:
            try:
                url = frame.url or ""
            except Exception:
                url = ""
            url_l = url.lower()
            s = 0
            if "uxiframe" in url_l:
                s += 3
            if "lpnlist" in url_l or "lpn" in url_l:
                s += 2
            if url and url != "about:blank":
                s += 1
            depth = len(frame.url.split("/")) if url else 0
            return (s, depth)

        frames = sorted(page.frames, key=score, reverse=True)

        for frame in frames:
            try:
                url = frame.url or ""
            except Exception:
                url = ""
            app_log(f"🔎 Frame candidate: {url}")
            url_l = url.lower()
            if url and url != "about:blank" and ("uxiframe" in url_l or "lpn" in url_l):
                app_log(f"✅ Using frame with url: {url}")
                return frame

        app_log("⚠️ Falling back to main page (no matching frame found)")
        return None


class ViewStabilizer:
    """Utilities for waiting on view stability."""
    
    @staticmethod
    def wait_for_ext_mask(target, timeout_ms: int = 4000) -> bool:
        """Wait for ExtJS loading mask to disappear."""
        if WaitUtils.wait_for_mask_clear(target, timeout_ms=timeout_ms):
            return True
        try:
            WaitUtils.wait_brief(target)
        except Exception:
            pass
        return True

    @staticmethod
    def compute_view_hash(target) -> str | None:
        """Compute a coarse hash of the current view."""
        try:
            content = target.evaluate("() => document.body?.innerText || ''")
            return hashlib.sha1(content.encode("utf-8", "ignore")).hexdigest()
        except Exception:
            return None

    @staticmethod
    def wait_for_stable_view(
        target,
        *,
        stable_samples: int = 3,
        interval_ms: int = 250,
        timeout_ms: int = 5000,
    ) -> bool:
        """Poll the view hash until it stops changing."""
        last = None
        stable = 0
        deadline = time.time() + timeout_ms / 1000
        
        while time.time() < deadline:
            h = ViewStabilizer.compute_view_hash(target)
            if h and h == last:
                stable += 1
                if stable >= stable_samples:
                    return True
            else:
                stable = 1 if h else 0
                last = h
            WaitUtils.wait_brief(target)
        
        rf_log("⚠️ View did not stabilize in time")
        return False

    @staticmethod
    def maximize_page_for_capture(page: Any):
        """Best-effort maximize/bring-to-front before screenshots."""
        try:
            deadline = time.time() + 3
            while time.time() < deadline:
                try:
                    if page.evaluate("document.readyState") == "complete":
                        break
                except Exception:
                    pass
                WaitUtils.wait_brief(page)
        except Exception:
            pass
        
        try:
            page.evaluate("""
                () => {
                    try {
                        window.moveTo(0, 0);
                        window.resizeTo(screen.availWidth, screen.availHeight);
                    } catch (e) {}
                }
            """)
        except Exception:
            pass


class ExtJSGridHelper:
    """ExtJS grid operations."""
    
    @staticmethod
    def get_store_count(target) -> int | None:
        """Get grid store count via ExtJS."""
        try:
            return target.evaluate(EXT_STORE_COUNT_SCRIPT)
        except Exception:
            return None

    @staticmethod
    def open_first_row(target) -> bool:
        """Use ExtJS APIs to select and open the first row."""
        try:
            return bool(target.evaluate(EXT_OPEN_FIRST_ROW_SCRIPT))
        except Exception:
            return False

    @staticmethod
    def get_statusbar_count(target) -> int | None:
        """Parse the grid status bar text for row counts."""
        try:
            bar = target.locator(
                "div.x-paging-info:visible, div[id*='pagingtoolbar']:visible .x-toolbar-text"
            ).last
            text = bar.inner_text(timeout=800)
        except Exception:
            return None

        m = re.search(r"of\s+(\d+)", text or "", re.I)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
        return None


class DOMRowOpener:
    """DOM-based row finding and opening."""
    
    @staticmethod
    def open_ilpn_row(target, ilpn: str) -> bool:
        """DOM fallback: search nested uxiframe tables for the ILPN and open it."""
        app_log(f"🐛 DEBUG: _dom_open_ilpn_row called for iLPN: {ilpn}")
        
        try:
            result = target.evaluate(DOM_OPEN_ILPN_ROW_SCRIPT, ilpn)
        except Exception as exc:
            rf_log(f"❌ DOM iLPN search failed: {exc}")
            app_log(f"🐛 DEBUG: _dom_open_ilpn_row exception: {exc}")
            return False

        app_log(f"🐛 DEBUG: _dom_open_ilpn_row result: {result}")

        if result and result.get("ok"):
            tbl = result.get("tableIdx")
            row = result.get("rowIdx")
            app_log(
                f"✅ Opened iLPN row via DOM fallback "
                f"(table#{tbl} row#{row}, iframe={result.get('iframeId')})"
            )
            return True

        if result:
            rf_log(
                f"❌ DOM iLPN search found no match "
                f"(iframe={result.get('iframeId')}, tables={result.get('tables')}, "
                f"reason={result.get('reason')})"
            )
        else:
            rf_log("❌ DOM iLPN search failed without result payload")

        return False


class TabNavigator:
    """Handles clicking through iLPN detail tabs."""
    
    TAB_NAMES = ["Header", "Contents", "Locks"]

    @staticmethod
    def diagnose_tabs(target):
        """Diagnostic function for tab detection."""
        if not getattr(Settings.app, "app_verbose_logging", False):
            app_log("ℹ️ Tab diagnostic skipped (APP_VERBOSE_LOGGING disabled)")
            return

        app_log("🔍 Starting comprehensive tab diagnostic...")
        is_page = hasattr(target, 'frames')
        app_log(f"📄 Target type: {'Page' if is_page else 'Frame'}")

        try:
            app_log("📄 Checking main target...")
            main_result = target.evaluate("""
                () => ({
                    url: window.location.href,
                    title: document.title,
                    frameCount: document.querySelectorAll('iframe').length,
                    bodyText: document.body?.innerText?.substring(0, 200) || 'NO BODY',
                })
            """)
            app_log(f"  Main info: {main_result}")
        except Exception as e:
            app_log(f"  ❌ Main check failed: {e}")

        if is_page:
            TabNavigator._diagnose_page_frames(target)

        app_log("\n✅ Diagnostic complete")

    @staticmethod
    def _diagnose_page_frames(target):
        """Diagnose frames within a page."""
        try:
            frames = target.frames
            app_log(f"📦 Total frames found: {len(frames)}")

            for idx, frame in enumerate(frames):
                try:
                    url = frame.url
                    app_log(f"\n🔲 Frame {idx}: {url}")
                    frame_info = frame.evaluate(TAB_DIAGNOSTIC_SCRIPT)

                    if frame_info['potentialTabs']:
                        app_log(f"  ✅ Found {len(frame_info['potentialTabs'])} potential tabs")
                        for tab in frame_info['potentialTabs']:
                            app_log(f"    📌 {tab}")
                except Exception as e:
                    app_log(f"  ❌ Frame {idx} check failed: {e}")
        except Exception as e:
            app_log(f"❌ Frame enumeration failed: {e}")

    @staticmethod
    def click_detail_tabs(target, config: TabClickConfig) -> bool:
        """Click through all visible iLPN detail tabs sequentially."""
        TabNavigator.diagnose_tabs(target)

        # Wait for tab panel to be ready
        app_log("⏳ Waiting for tab panel to be fully loaded...")
        TabNavigator._wait_for_tab_panel_ready(target)
        WaitUtils.wait_brief(target)

        app_log("🎯 Starting tab clicking process...")

        frames_to_try = TabNavigator._collect_frames(target)
        use_page = getattr(target, "page", None) or target
        base_note = config.operation_note or "iLPN detail tab"
        tab_images: list[bytes] = []

        ViewStabilizer.maximize_page_for_capture(use_page)

        for tab_name in TabNavigator.TAB_NAMES:
            app_log(f"\n🔄 Attempting to click tab: {tab_name}")
            clicked = TabNavigator._click_single_tab(
                tab_name, frames_to_try, config.click_timeout_ms
            )

            if clicked:
                # Wait for ExtJS to process the tab change and load content
                app_log(f"  ⏳ Waiting for tab '{tab_name}' content to load...")

                # Wait for loading mask to clear
                ViewStabilizer.wait_for_ext_mask(target, timeout_ms=3000)

                # Wait for DOM to stabilize after tab change
                if not ViewStabilizer.wait_for_stable_view(target, stable_samples=2, interval_ms=300, timeout_ms=4000):
                    app_log(f"  ⚠️ Tab '{tab_name}' content did not stabilize, but continuing...")

                # Additional brief wait for any animations
                WaitUtils.wait_brief(target)

                # Verify the tab is actually active
                is_active = TabNavigator._verify_tab_active(target, tab_name)
                if is_active:
                    app_log(f"  ✅ Tab '{tab_name}' is active and content loaded")
                else:
                    app_log(f"  ⚠️ Could not verify tab '{tab_name}' is active")

                if config.screenshot_mgr:
                    try:
                        img_bytes = use_page.screenshot(full_page=True, type="jpeg")
                        tab_images.append(img_bytes)
                    except Exception as exc:
                        app_log(f"⚠️ Could not capture tab {tab_name}: {exc}")
            else:
                app_log(f"  ❌ FAILED to click tab: {tab_name}")

        app_log("\n✅ Tab clicking process complete")
        
        if config.capture_after_tabs and config.screenshot_mgr:
            TabNavigator._capture_combined_tabs(
                use_page, tab_images, config, base_note
            )
        
        return True

    @staticmethod
    def _verify_tab_active(target, tab_name: str) -> bool:
        """Verify that a tab is actually active after clicking."""
        try:
            result = target.evaluate("""
                (tabName) => {
                    // Method 1: Check ExtJS active tab
                    if (window.Ext?.ComponentQuery) {
                        const tabPanels = Ext.ComponentQuery.query('tabpanel');
                        for (const panel of tabPanels) {
                            if (panel.isHidden?.() || panel.isDestroyed?.()) continue;

                            const activeTab = panel.getActiveTab?.();
                            if (activeTab) {
                                const title = activeTab.title || activeTab.tab?.text || '';
                                if (title === tabName || title.startsWith(tabName)) {
                                    return { active: true, method: 'extjs', title };
                                }
                            }
                        }
                    }

                    // Method 2: Check aria-selected attribute
                    const ariaTabs = document.querySelectorAll('[role="tab"][aria-selected="true"]');
                    for (const tab of ariaTabs) {
                        const text = tab.textContent?.trim();
                        if (text === tabName || text?.startsWith(tabName)) {
                            return { active: true, method: 'aria-selected', text };
                        }
                    }

                    // Method 3: Check active/selected class
                    const activeSelectors = [
                        '.x-tab-strip-active',
                        '.x-tab-active',
                        '.active[role="tab"]',
                        'li.x-tab-strip-active'
                    ];

                    for (const selector of activeSelectors) {
                        const tabs = document.querySelectorAll(selector);
                        for (const tab of tabs) {
                            const text = tab.textContent?.trim();
                            if (text === tabName || text?.startsWith(tabName)) {
                                return { active: true, method: 'class-' + selector, text };
                            }
                        }
                    }

                    return { active: false, reason: 'not-found-active' };
                }
            """, tab_name)

            if result and result.get('active'):
                method = result.get('method', 'unknown')
                app_log(f"    ✓ Verified active via {method}")
                return True
            else:
                reason = result.get('reason', 'unknown') if result else 'no-result'
                app_log(f"    ✗ Not verified active: {reason}")
                return False

        except Exception as e:
            app_log(f"    ⚠️ Tab verification failed: {e}")
            return False

    @staticmethod
    def _wait_for_tab_panel_ready(target, timeout_ms: int = 5000) -> bool:
        """Wait for ExtJS tab panel to be fully rendered and ready."""
        deadline = time.time() + timeout_ms / 1000

        while time.time() < deadline:
            try:
                # Check if ExtJS tab panel exists and is rendered
                result = target.evaluate("""
                    () => {
                        if (!window.Ext?.ComponentQuery) return { ready: false, reason: 'no-extjs' };

                        const tabPanels = Ext.ComponentQuery.query('tabpanel');
                        if (!tabPanels.length) return { ready: false, reason: 'no-tabpanel' };

                        for (const panel of tabPanels) {
                            if (panel.isHidden?.() || panel.isDestroyed?.()) continue;
                            if (!panel.rendered) continue;

                            const items = panel.items?.items || [];
                            if (items.length > 0) {
                                return { ready: true, tabCount: items.length, panelId: panel.id };
                            }
                        }

                        return { ready: false, reason: 'no-tabs' };
                    }
                """)

                if result and result.get('ready'):
                    app_log(f"  ✅ Tab panel ready with {result.get('tabCount', 0)} tabs")
                    return True

                app_log(f"  ⏳ Tab panel not ready yet: {result.get('reason', 'unknown')}")

            except Exception as e:
                app_log(f"  ⚠️ Tab panel check failed: {e}")

            WaitUtils.wait_brief(target)

        app_log("  ⚠️ Tab panel did not become ready in time, proceeding anyway")
        return False

    @staticmethod
    def _collect_frames(target) -> list:
        """Collect all frames to try for tab clicking."""
        frames_to_try = [target]
        try:
            for frame in target.frames:
                frames_to_try.append(frame)
                try:
                    app_log(f"  📦 Will try frame: {frame.url}")
                except Exception:
                    app_log("  📦 Will try frame: (no url)")
        except Exception as e:
            app_log(f"⚠️ Could not enumerate frames: {e}")
        return frames_to_try

    @staticmethod
    def _click_single_tab(tab_name: str, frames: list, timeout_ms: int) -> bool:
        """Attempt to click a single tab across all frames with retry logic."""
        max_retries = 3

        for retry in range(max_retries):
            if retry > 0:
                wait_time = min(500 * (2 ** (retry - 1)), 2000)  # Exponential backoff: 500ms, 1000ms, 2000ms
                app_log(f"  🔄 Retry {retry}/{max_retries}, waiting {wait_time}ms...")
                time.sleep(wait_time / 1000)

            for frame_idx, page_target in enumerate(frames):
                try:
                    app_log(f"  🎯 Trying in frame {frame_idx} (attempt {retry + 1})...")

                    # Strategy 1: JavaScript evaluation (try ExtJS first, then DOM)
                    result = TabNavigator._try_js_click(page_target, tab_name)
                    if result:
                        app_log(f"  ✅ Tab clicked successfully via JS in frame {frame_idx}")
                        return True

                    # Strategy 2: Playwright text matching (fallback)
                    if TabNavigator._try_playwright_click(page_target, tab_name, timeout_ms):
                        app_log(f"  ✅ Tab clicked successfully via Playwright in frame {frame_idx}")
                        return True

                except Exception as e:
                    app_log(f"  ⚠️ Frame {frame_idx} attempt {retry + 1} failed: {e}")

        app_log(f"  ❌ Failed to click tab '{tab_name}' after {max_retries} retries across all frames")
        return False

    @staticmethod
    def _try_playwright_click(page_target, tab_name: str, timeout_ms: int) -> bool:
        """Try clicking tab using Playwright's text matching."""
        try:
            elements = page_target.get_by_text(tab_name, exact=True)
            count = elements.count()
            app_log(f"    Found {count} exact text matches")

            for i in range(count):
                try:
                    el = elements.nth(i)
                    el.scroll_into_view_if_needed(timeout=timeout_ms)
                    el.click(force=True, timeout=timeout_ms)
                    app_log(f"    ✅ Clicked element {i}")
                    return True
                except Exception as e:
                    app_log(f"    ⚠️ Element {i} click failed: {e}")
        except Exception as e:
            app_log(f"    ⚠️ Text match strategy failed: {e}")
        return False

    @staticmethod
    def _try_js_click(page_target, tab_name: str) -> bool:
        """Try clicking tab using JavaScript evaluation."""
        try:
            result = page_target.evaluate(TAB_CLICK_SCRIPT, tab_name)

            # Log detailed diagnostics
            if result.get('log'):
                for log_entry in result['log']:
                    app_log(f"      📝 JS: {log_entry}")

            if result.get('success'):
                method = result.get('method') or result.get('strategy', 'unknown')
                confirmed = result.get('confirmed', False)

                if confirmed:
                    app_log(f"    ✅ JS click succeeded via {method} (confirmed active): {result.get('text', tab_name)}")
                    return True
                else:
                    # Click reported success but tab not confirmed active - treat as partial success
                    app_log(f"    ⚠️ JS click via {method} but tab not confirmed active: {result.get('text', tab_name)}")
                    # Still return True because click happened, Python will verify separately
                    return True
            else:
                reason = result.get('reason', 'unknown')
                app_log(f"    ⚠️ JS click failed: {reason}")
        except Exception as e:
            app_log(f"    ⚠️ JS strategy exception: {e}")
        return False

    @staticmethod
    def _capture_combined_tabs(
        use_page, 
        tab_images: list[bytes], 
        config: TabClickConfig,
        base_note: str
    ):
        """Capture combined screenshot of all tabs."""
        safe_tag = config.screenshot_tag or "ilpn_tab"
        screenshot_mgr = config.screenshot_mgr
        
        if not screenshot_mgr:
            return
            
        try:
            if not tab_images:
                screenshot_mgr.capture(use_page, f"{safe_tag}_combined", f"{base_note}: all tabs")
                return
                
            from PIL import Image, ImageDraw, ImageFont

            images = [Image.open(BytesIO(b)) for b in tab_images if b]
            if not images:
                screenshot_mgr.capture(use_page, f"{safe_tag}_combined", f"{base_note}: all tabs")
                return

            combined = TabNavigator._stitch_images(images)
            combined = TabNavigator._add_overlays(combined, screenshot_mgr, base_note)
            
            screenshot_mgr.sequence += 1
            filename = screenshot_mgr._build_filename(f"{safe_tag}_combined")
            fmt = "JPEG" if screenshot_mgr.image_format == "jpeg" else "PNG"
            save_kwargs = {"quality": screenshot_mgr.image_quality} if fmt == "JPEG" and screenshot_mgr.image_quality else {}
            combined.save(filename, format=fmt, **save_kwargs)
            app_log(f"📸 Combined tab screenshot saved: {filename}")
            
        except Exception as exc:
            app_log(f"⚠️ Combined tab capture failed: {exc}")

    @staticmethod
    def _stitch_images(images: list) -> "Image":
        """Stitch multiple images vertically."""
        from PIL import Image
        
        widths, heights = zip(*(img.size for img in images))
        combined_height = sum(heights)
        max_width = max(widths)
        combined = Image.new("RGB", (max_width, combined_height), "white")

        y = 0
        for img in images:
            combined.paste(img, (0, y))
            y += img.height
            
        return combined

    @staticmethod
    def _add_overlays(combined: "Image", screenshot_mgr, base_note: str) -> "Image":
        """Add text overlays to combined image."""
        from PIL import Image, ImageDraw, ImageFont
        
        try:
            overlay_parts = []
            scenario = getattr(screenshot_mgr, "current_scenario_label", None)
            stage = getattr(screenshot_mgr, "current_stage_label", None)
            if scenario:
                overlay_parts.append(str(scenario))
            if stage:
                overlay_parts.append(str(stage))
            if base_note:
                overlay_parts.append(str(base_note))
            overlay_text = " / ".join(part for part in overlay_parts if part)
            timestamp_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            font = ImageFont.load_default()
            overlay = Image.new("RGBA", combined.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            padding = 10

            if overlay_text:
                text_bbox = font.getbbox(overlay_text)
                tw = text_bbox[2] - text_bbox[0]
                th = text_bbox[3] - text_bbox[1]
                top = padding
                left = max(padding, (combined.width - tw) // 2 - padding)
                box = (left, top, left + tw + padding * 2, top + th + padding * 2)
                draw.rectangle(box, fill=(255, 255, 255, 180))
                draw.text((left + padding, top + padding), overlay_text, fill="black", font=font)

            ts_bbox = font.getbbox(timestamp_text)
            tsw = ts_bbox[2] - ts_bbox[0]
            tsh = ts_bbox[3] - ts_bbox[1]
            box = (
                combined.width - tsw - padding * 2,
                combined.height - tsh - padding * 2,
                combined.width - padding // 2,
                combined.height - padding // 2,
            )
            draw.rectangle(box, fill=(255, 255, 255, 200))
            draw.text((box[0] + padding // 2, box[1] + padding // 2), timestamp_text, fill="black", font=font)

            return Image.alpha_composite(combined.convert("RGBA"), overlay).convert("RGB")
        except Exception as exc:
            app_log(f"⚠️ Failed to add overlay to combined image: {exc}")
            return combined


class FilteredRowOpener:
    """Opens filtered iLPN rows."""
    
    GRID_SELECTORS = [
        "div.x-grid-view:visible",
        "div[class*='x-grid-view']:visible",
        "//div[contains(@class,'x-grid-view') and not(contains(@class,'x-hide'))]",
        "table.x-grid-table:visible",
    ]

    @staticmethod
    def open_single_row(
        target,
        ilpn: str,
        screenshot_mgr: ScreenshotManager | None = None,
        *,
        tab_click_timeout_ms: int | None = None,
        drill_detail: bool = False,
    ) -> bool:
        """Open the filtered iLPN row."""
        app_log("🔍 Checking filtered iLPN results (no long wait)...")
        ViewStabilizer.wait_for_ext_mask(target, timeout_ms=3000)

        tab_config = TabClickConfig(
            screenshot_mgr=screenshot_mgr,
            screenshot_tag="ilpn_tab",
            operation_note=f"iLPN {ilpn} detail tabs",
            click_timeout_ms=tab_click_timeout_ms or 3000,
        )

        # Fast path: DOM scan
        if DOMRowOpener.open_ilpn_row(target, ilpn):
            WaitUtils.wait_brief(target)
            if drill_detail:
                TabNavigator.click_detail_tabs(target, tab_config)
            return True

        # Detect row count
        row_count, rows_locator = FilteredRowOpener._detect_rows(target)

        # Try ExtJS-native open
        if row_count == 1 and ExtJSGridHelper.open_first_row(target):
            app_log("✅ Opened single iLPN row via ExtJS API")
            WaitUtils.wait_brief(target)
            if drill_detail:
                TabNavigator.click_detail_tabs(target, tab_config)
            return True

        # DOM fallback retry
        if DOMRowOpener.open_ilpn_row(target, ilpn):
            WaitUtils.wait_brief(target)
            if drill_detail:
                TabNavigator.click_detail_tabs(target, tab_config)
            return True

        # Final locator-based attempt
        if row_count == 1 and rows_locator:
            if FilteredRowOpener._try_locator_open(target, rows_locator, tab_config, tab_click_timeout_ms, drill_detail):
                return True

        rf_log(f"❌ Unable to open the filtered iLPN row (row_count={row_count})")
        return False

    @staticmethod
    def _detect_rows(target) -> tuple[int, Any]:
        """Detect row count using multiple strategies."""
        rows_locator = None
        row_count = 0
        
        for attempt in range(4):
            ext_count = ExtJSGridHelper.get_store_count(target)
            if isinstance(ext_count, int):
                row_count = ext_count

            status_count = ExtJSGridHelper.get_statusbar_count(target)
            if isinstance(status_count, int) and status_count > row_count:
                row_count = status_count

            for sel in FilteredRowOpener.GRID_SELECTORS:
                try:
                    grid = target.locator(sel).last
                    grid.wait_for(state="visible", timeout=1200)
                except Exception:
                    continue

                rows_locator = grid.locator(".x-grid-row:visible, .x-grid-item:visible, tr.x-grid-row")
                css_count = rows_locator.count()
                if css_count:
                    row_count = max(row_count, css_count)
                    break

            if row_count == 1:
                break
            if row_count > 1:
                app_log(f"ℹ️ Filter shows {row_count} rows; retrying quickly...")
            WaitUtils.wait_brief(target)
            
        return row_count, rows_locator

    @staticmethod
    def _try_locator_open(target, rows_locator, tab_config: TabClickConfig, timeout_ms: int | None, drill_detail: bool) -> bool:
        """Try opening row using locator-based methods."""
        row = rows_locator.first
        try:
            row.scroll_into_view_if_needed(timeout=timeout_ms or 3000)
        except Exception:
            pass
        try:
            row.click(timeout=1500)
        except Exception as exc:
            app_log(f"➖ Row click warning: {exc}")

        open_attempts = [
            lambda: row.dblclick(timeout=2000),
            lambda: row.press("Enter"),
            lambda: row.press("Space"),
            lambda: target.keyboard.press("Enter"),
        ]

        for idx, attempt in enumerate(open_attempts):
            try:
                attempt()
                app_log("✅ Opened single iLPN row to view details")
                if not ViewStabilizer.wait_for_stable_view(target):
                    app_log("⚠️ Detail view not stable after open; retrying")
                    continue
                WaitUtils.wait_brief(target)
                if drill_detail:
                    TabNavigator.click_detail_tabs(target, tab_config)
                ViewStabilizer.wait_for_stable_view(target)
                return True
            except Exception as exc:
                app_log(f"➖ Row open attempt {idx + 1} did not succeed: {exc}")

        return False


class ILPNFilterFiller:
    """Main class for filling iLPN filters."""
    
    INPUT_CANDIDATES = [
        "//input[contains(@name,'filter') and not(@type='hidden')]",
        "input.x-form-text:visible",
        "input[type='text']:visible",
    ]

    @staticmethod
    def fill_filter(
        page,
        ilpn: str,
        screenshot_mgr: ScreenshotManager | None = None,
        *,
        tab_click_timeout_ms: int | None = None,
        drill_detail: bool = False,
    ) -> bool:
        """Populate the iLPN quick filter and open the matching row."""
        target_frame = FrameFinder.find_ilpn_frame(page)
        target = target_frame or page

        if not target_frame:
            rf_log("⚠️ Could not locate dedicated iLPNs frame, using active page as fallback.")

        filter_triggered = ILPNFilterFiller._fill_input(target, ilpn)

        if not filter_triggered:
            filter_triggered = ILPNFilterFiller._try_hidden_fill(target, ilpn)

        if not filter_triggered:
            rf_log("❌ Unable to trigger iLPN filter apply")
            return False

        return FilteredRowOpener.open_single_row(
            target,
            ilpn,
            screenshot_mgr=screenshot_mgr,
            tab_click_timeout_ms=tab_click_timeout_ms,
            drill_detail=drill_detail,
        )

    @staticmethod
    def _fill_input(target, ilpn: str) -> bool:
        """Try to fill visible input field."""
        input_field = ILPNFilterFiller._find_input(target)
        
        if not input_field:
            return False
            
        try:
            app_log("✏️ Filling visible input and pressing Enter")
            input_field.click()
            input_field.fill(ilpn)
            input_field.press("Enter")
        except Exception as exc:
            rf_log(f"❌ Unable to fill iLPN filter: {exc}")
            return False

        return ILPNFilterFiller._click_apply(target)

    @staticmethod
    def _find_input(target) -> Any | None:
        """Find visible input field."""
        for sel in ILPNFilterFiller.INPUT_CANDIDATES:
            app_log(f"🔎 Trying selector: {sel}")
            try:
                locator = target.locator(sel).first
                locator.wait_for(state="visible", timeout=3000)
                state = locator.evaluate("""
                    el => ({
                        display: getComputedStyle(el).display,
                        visibility: getComputedStyle(el).visibility,
                        disabled: el.disabled,
                        readonly: el.readOnly
                    })
                """)
                app_log(f"✅ Selector matched: {sel} (state={state})")
                return locator
            except Exception as exc:
                app_log(f"➖ Selector not usable: {sel} ({exc})")
        return None

    @staticmethod
    def _try_hidden_fill(target, ilpn: str) -> bool:
        """Try hidden input fill fallback."""
        rf_log("⚠️ Could not locate visible iLPN quick filter input, attempting hidden-fill fallback.")
        
        try:
            filled = target.evaluate(HIDDEN_INPUT_FILL_SCRIPT, ilpn)
            if filled:
                try:
                    target.press("body", "Enter")
                    target.press("body", "Space")
                except Exception:
                    pass
                app_log("✅ Hidden candidate filled and keyboard events fired (Enter/Space).")
                return True
        except Exception as exc:
            rf_log(f"❌ Hidden iLPN fill fallback failed: {exc}")
            
        return False

    @staticmethod
    def _click_apply(target) -> bool:
        """Click the Apply button."""
        apply_candidates = [
            target.get_by_role("button", name="Apply"),
            target.locator("//a[.//span[normalize-space()='Apply']]"),
            target.locator("//button[normalize-space()='Apply']"),
            target.locator("//span[normalize-space()='Apply']"),
        ]
        
        for btn in apply_candidates:
            try:
                btn.first.click()
                app_log("✅ Clicked Apply candidate")
                return True
            except Exception as exc:
                app_log(f"➖ Apply candidate not clickable: {exc}")

        # Keyboard fallback
        try:
            target.press("body", "Tab")
            target.press("body", "Tab")
            target.press("body", "Enter")
            target.press("body", "Space")
            app_log("⌨️ Used keyboard fallback (Tab Tab Enter Space)")
            return True
        except Exception as exc:
            rf_log(f"❌ Unable to click Apply (even with keyboard fallback): {exc}")
            
        return False


# =============================================================================
# PUBLIC API - Backward compatible functions
# =============================================================================

def fill_ilpn_filter(
    page,
    ilpn: str,
    screenshot_mgr: ScreenshotManager | None = None,
    *,
    tab_click_timeout_ms: int | None = None,
    drill_detail: bool = False,
) -> bool:
    """Populate the iLPN quick filter and open the matching row.

    This is the main public API - maintains backward compatibility.
    """
    return ILPNFilterFiller.fill_filter(
        page, ilpn, screenshot_mgr, tab_click_timeout_ms=tab_click_timeout_ms, drill_detail=drill_detail
    )


# Legacy function aliases for backward compatibility
_find_ilpn_frame = FrameFinder.find_ilpn_frame
_wait_for_ext_mask = ViewStabilizer.wait_for_ext_mask
_compute_view_hash = ViewStabilizer.compute_view_hash
_wait_for_stable_view = ViewStabilizer.wait_for_stable_view
_maximize_page_for_capture = ViewStabilizer.maximize_page_for_capture
_ext_store_count = ExtJSGridHelper.get_store_count
_ext_open_first_row = ExtJSGridHelper.open_first_row
_statusbar_count = ExtJSGridHelper.get_statusbar_count
_dom_open_ilpn_row = DOMRowOpener.open_ilpn_row
_diagnose_tabs = TabNavigator.diagnose_tabs
_click_ilpn_detail_tabs = lambda target, **kw: TabNavigator.click_detail_tabs(
    target, TabClickConfig(**kw)
)
_open_single_filtered_ilpn_row = FilteredRowOpener.open_single_row
