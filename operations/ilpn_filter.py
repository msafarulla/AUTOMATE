"""
Shared iLPN helpers: quick filter fill, row open, diagnostics, and tab clicking.

This is a library-only copy of the debug helper logic to avoid circular imports.
"""

import re
import time
from typing import Any

from core.logger import app_log, rf_log
from core.screenshot import ScreenshotManager


def _find_ilpn_frame(page):
    """
    Locate the frame that hosts the iLPNs grid.
    """
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

    frames = list(page.frames)
    frames.sort(key=score, reverse=True)

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


def _wait_for_ext_mask(target, timeout_ms: int = 4000):
    """Wait for ExtJS loading mask to disappear."""
    mask = target.locator("div.x-mask:visible")
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        try:
            if mask.count() == 0:
                return True
        except Exception:
            return True
        target.wait_for_timeout(150)
    return True


def _ext_store_count(target) -> int | None:
    """Get grid store count via ExtJS if available."""
    try:
        return target.evaluate(
            """
            () => {
                if (!window.Ext?.ComponentQuery) return null;
                const grids = Ext.ComponentQuery.query('grid') || [];
                for (let i = grids.length - 1; i >= 0; i -= 1) {
                    const g = grids[i];
                    try {
                        if (g.isHidden?.() || g.isDestroyed?.()) continue;
                        const cnt = g.getStore?.()?.getCount?.();
                        if (typeof cnt === 'number') return cnt;
                    } catch (e) {}
                }
                return null;
            }
            """
        )
    except Exception:
        return None


def _ext_open_first_row(target) -> bool:
    """Use ExtJS APIs to select and open the first row."""
    try:
        return bool(
            target.evaluate(
                """
                () => {
                    if (!window.Ext?.ComponentQuery) return false;
                    const grids = Ext.ComponentQuery.query('grid') || [];
                    for (let i = grids.length - 1; i >= 0; i -= 1) {
                        const g = grids[i];
                        try {
                            if (g.isHidden?.() || g.isDestroyed?.()) continue;
                            const store = g.getStore?.();
                            if (!store || store.getCount?.() !== 1) continue;
                            const rec = store.getAt?.(0);
                            if (!rec) continue;

                            const sel = g.getSelectionModel?.();
                            sel?.select(rec);

                            const view = g.getView?.();
                            const row = view?.getRow?.(rec) || view?.getNode?.(0);
                            if (row) {
                                row.scrollIntoView({ block: 'center' });
                                row.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 1 }));
                                row.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, detail: 2 }));
                                return true;
                            }
                        } catch (e) {}
                    }
                    return false;
                }
                """
            )
        )
    except Exception:
        return False


def _statusbar_count(target) -> int | None:
    """Parse the grid status bar text for row counts (e.g., 'Displaying 1 - 1 of 1')."""
    try:
        bar = target.locator("div.x-paging-info:visible, div[id*='pagingtoolbar']:visible .x-toolbar-text").last
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


def _dom_open_ilpn_row(target, ilpn: str) -> bool:
    """DOM fallback: search nested uxiframe tables for the ILPN and open it."""
    app_log(f"🐛 DEBUG: _dom_open_ilpn_row called for iLPN: {ilpn}")
    try:
        result = target.evaluate(
            """
            (ilpn) => {
                console.log('DOM search starting for:', ilpn);
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                const digits = (s) => (s || '').replace(/\\D+/g, '');
                const containsIlpn = (txt) => {
                    const t = norm(txt);
                    if (!t) return false;
                    return t.includes(ilpn) || digits(t).includes(digits(ilpn));
                };

                const seenDocs = new Set();
                const docsToScan = [];

                const pushDoc = (doc) => {
                    if (doc && !seenDocs.has(doc)) {
                        seenDocs.add(doc);
                        docsToScan.push(doc);
                    }
                };

                pushDoc(document);
                Array.from(document.querySelectorAll('iframe')).forEach(ifr => {
                    try { pushDoc(ifr.contentDocument); } catch (e) {}
                });

                let hit = null;
                let lastIframeId = null;
                let lastIframeSrc = null;
                let scannedTables = 0;

                for (const doc of docsToScan) {
                    const ownerFrame = doc.defaultView?.frameElement;
                    lastIframeId = ownerFrame?.id || null;
                    lastIframeSrc = ownerFrame?.src || null;

                    const tables = Array.from(doc.querySelectorAll('table'));
                    scannedTables += tables.length;

                    for (let tblIdx = 0; tblIdx < tables.length; tblIdx += 1) {
                        const tbl = tables[tblIdx];
                        const rows = Array.from(tbl.querySelectorAll('tr'));
                        for (let rowIdx = 0; rowIdx < rows.length; rowIdx += 1) {
                            const row = rows[rowIdx];
                            const cells = Array.from(row.querySelectorAll('td, th'));
                            if (!cells.length) continue;
                            const rowText = cells.map(c => norm(c.textContent)).join(' ').trim();
                            if (!rowText) continue;
                            if (containsIlpn(rowText)) {
                                try {
                                    row.scrollIntoView({ block: 'center' });
                                    row.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 1 }));
                                    row.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, detail: 2 }));
                                } catch (e) {}

                                hit = {
                                    iframeId: lastIframeId,
                                    iframeSrc: lastIframeSrc,
                                    tableIdx: tblIdx,
                                    rowIdx: rowIdx,
                                };
                                break;
                            }
                        }
                        if (hit) break;
                    }
                    if (hit) break;
                }

                return {
                    ok: !!hit,
                    iframeId: hit?.iframeId || lastIframeId,
                    iframeSrc: hit?.iframeSrc || lastIframeSrc,
                    tableIdx: hit?.tableIdx,
                    rowIdx: hit?.rowIdx,
                    tables: scannedTables,
                    reason: hit ? 'found' : 'not-found',
                };
            }
            """,
            ilpn,
        )
    except Exception as exc:
        rf_log(f"❌ DOM iLPN search failed: {exc}")
        app_log(f"🐛 DEBUG: _dom_open_ilpn_row exception: {exc}")
        return False

    app_log(f"🐛 DEBUG: _dom_open_ilpn_row result: {result}")

    if result and result.get("ok"):
        tbl = result.get("tableIdx")
        row = result.get("rowIdx")
        app_log(
            f"✅ Opened iLPN row via DOM fallback (table#{tbl} row#{row}, iframe={result.get('iframeId')})"
        )
        app_log("🐛 DEBUG: _dom_open_ilpn_row returning True")
        return True

    if result:
        rf_log(
            f"❌ DOM iLPN search found no match "
            f"(iframe={result.get('iframeId')}, tables={result.get('tables')}, reason={result.get('reason')})"
        )
    else:
        rf_log("❌ DOM iLPN search failed without result payload")

    app_log("🐛 DEBUG: _dom_open_ilpn_row returning False")
    return False


def _open_single_filtered_ilpn_row(
    target,
    ilpn: str,
    screenshot_mgr: ScreenshotManager | None = None,
) -> bool:
    """
    Open the filtered iLPN row quickly.
    """
    app_log("🔍 Checking filtered iLPN results (no long wait)...")
    app_log("🐛 DEBUG: Entered _open_single_filtered_ilpn_row")
    _wait_for_ext_mask(target, timeout_ms=3000)

    tab_capture_kwargs = {
        "screenshot_mgr": screenshot_mgr,
        "screenshot_tag": "ilpn_tab",
        "operation_note": f"iLPN {ilpn} detail tabs",
    }

    # Fast path: DOM scan
    app_log("🐛 DEBUG: Attempting DOM open...")
    if _dom_open_ilpn_row(target, ilpn):
        app_log("🐛 DEBUG: DOM open succeeded, about to call _click_ilpn_detail_tabs")
        target.wait_for_timeout(2000)
        _click_ilpn_detail_tabs(target, **tab_capture_kwargs)
        app_log("🐛 DEBUG: Returned from _click_ilpn_detail_tabs")
        return True
    else:
        app_log("🐛 DEBUG: DOM open failed, trying other methods...")

    selectors = [
        "div.x-grid-view:visible",
        "div[class*='x-grid-view']:visible",
        "//div[contains(@class,'x-grid-view') and not(contains(@class,'x-hide'))]",
        "table.x-grid-table:visible",
    ]

    rows_locator = None
    row_count = 0
    for attempt in range(4):
        app_log(f"🐛 DEBUG: Attempt {attempt + 1} to detect rows...")
        ext_count = _ext_store_count(target)
        if isinstance(ext_count, int):
            row_count = ext_count
            app_log(f"🐛 DEBUG: ExtJS store count = {row_count}")
        else:
            row_count = 0

        status_count = _statusbar_count(target)
        if isinstance(status_count, int) and status_count > row_count:
            row_count = status_count
            app_log(f"🐛 DEBUG: Status bar count = {row_count}")

        for sel in selectors:
            try:
                grid = target.locator(sel).last
                grid.wait_for(state="visible", timeout=1200)
            except Exception:
                continue

            rows_locator = grid.locator(
                ".x-grid-row:visible, .x-grid-item:visible, tr.x-grid-row"
            )
            css_count = rows_locator.count()
            if css_count:
                row_count = max(row_count, css_count)
                app_log(f"🐛 DEBUG: CSS row count = {css_count}, total = {row_count}")
                break

        if row_count == 1:
            app_log("🐛 DEBUG: Found exactly 1 row")
            break
        if row_count > 1:
            app_log(f"ℹ️ Filter shows {row_count} rows; retrying quickly...")
        target.wait_for_timeout(300)

    if row_count == 1 and _ext_open_first_row(target):
        app_log("✅ Opened single iLPN row via ExtJS API")
        app_log("🐛 DEBUG: About to call _click_ilpn_detail_tabs (ExtJS path)")
        target.wait_for_timeout(2000)
        _click_ilpn_detail_tabs(target, **tab_capture_kwargs)
        app_log("🐛 DEBUG: Returned from _click_ilpn_detail_tabs (ExtJS path)")
        return True

    app_log("🐛 DEBUG: Trying DOM open again after row detection...")
    if _dom_open_ilpn_row(target, ilpn):
        app_log("🐛 DEBUG: Second DOM open succeeded, about to call _click_ilpn_detail_tabs")
        target.wait_for_timeout(2000)
        _click_ilpn_detail_tabs(target, **tab_capture_kwargs)
        app_log("🐛 DEBUG: Returned from _click_ilpn_detail_tabs (DOM retry path)")
        return True

    if row_count == 1 and rows_locator:
        app_log("🐛 DEBUG: Trying locator-based row open...")
        row = rows_locator.first
        try:
            row.scroll_into_view_if_needed(timeout=1000)
        except Exception:
            pass
        try:
            row.click(timeout=1500)
            app_log("🐛 DEBUG: Row clicked successfully")
        except Exception as exc:
            app_log(f"➖ Row click warning: {exc}")
        open_attempts = [
            lambda: row.dblclick(timeout=1200),
            lambda: row.press("Enter"),
            lambda: row.press("Space"),
            lambda: target.keyboard.press("Enter"),
        ]
        for idx, attempt in enumerate(open_attempts):
            try:
                app_log(f"🐛 DEBUG: Trying open attempt {idx + 1}...")
                attempt()
                app_log("✅ Opened single iLPN row to view details")
                app_log("🐛 DEBUG: About to call _click_ilpn_detail_tabs (locator path)")
                target.wait_for_timeout(2000)
                _click_ilpn_detail_tabs(target, **tab_capture_kwargs)
                app_log("🐛 DEBUG: Returned from _click_ilpn_detail_tabs (locator path)")
                return True
            except Exception as exc:
                app_log(f"➖ Row open attempt {idx + 1} did not succeed: {exc}")
                continue
    app_log(f"🐛 DEBUG: All methods failed, row_count={row_count}")
    rf_log(f"❌ Unable to open the filtered iLPN row (row_count={row_count})")
    return False


def fill_ilpn_filter(
    page,
    ilpn: str,
    screenshot_mgr: ScreenshotManager | None = None,
) -> bool:
    """Populate the iLPN quick filter and open the result."""
    target_frame = _find_ilpn_frame(page)
    target = target_frame or page
    if not target_frame:
        rf_log("⚠️ Could not locate dedicated iLPNs frame, using active page as fallback.")

    filter_triggered = False
    candidates = [
        "//input[contains(@name,'filter') and not(@type='hidden')]",
        "input.x-form-text:visible",
        "input[type='text']:visible",
    ]
    input_field = None

    for sel in candidates:
        try:
            field = target.locator(sel).first
            count = field.count()
            if count == 0:
                continue
            field.wait_for(timeout=1500)
            if field.is_visible():
                input_field = field
                break
        except Exception:
            continue

    if not input_field:
        try:
            hidden_candidates = target.locator("//input[contains(@name,'filter') and @type='hidden']")
            if hidden_candidates.count():
                hidden = hidden_candidates.first
                value_before = hidden.input_value(timeout=500)
                app_log(f"🐛 DEBUG: Hidden iLPN value before fill: {value_before}")
                hidden.fill(ilpn)
                value_after = hidden.input_value(timeout=500)
                app_log(f"🐛 DEBUG: Hidden iLPN value after fill: {value_after}")
                if value_before != value_after:
                    filter_triggered = True
                try:
                    target.press("body", "Enter")
                except Exception:
                    pass
                try:
                    target.press("body", "Space")
                except Exception:
                    pass
                app_log("✅ Hidden candidate filled and keyboard events fired (Enter/Space).")
                filter_triggered = True
        except Exception as exc:
            rf_log(f"❌ Hidden iLPN fill fallback failed: {exc}")
            return False

        if not filter_triggered:
            rf_log("❌ Hidden iLPN fill fallback did not find a candidate.")
            return False

    if input_field:
        try:
            app_log("✏️ Filling visible input and pressing Enter")
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
            app_log("✅ Clicked Apply candidate")
            filter_triggered = True
            break
        except Exception as exc:
            app_log(f"➖ Apply candidate not clickable: {exc}")
            continue

    if not filter_triggered:
        try:
            target.press("body", "Tab")
            target.press("body", "Tab")
            target.type("body", ilpn)
            target.press("body", "Enter")
            target.press("body", "Space")
            app_log("⌨️ Used keyboard fallback (Tab Tab Enter Space)")
            filter_triggered = True
        except Exception as exc:
            rf_log(f"❌ Unable to click Apply in iLPNs UI (even with keyboard fallback): {exc}")
            return False

    if not filter_triggered:
        rf_log("❌ Unable to trigger iLPN filter apply")
        return False

    return _open_single_filtered_ilpn_row(target, ilpn, screenshot_mgr=screenshot_mgr)


def _diagnose_tabs(target):
    """Diagnostic function - handles both Page and Frame objects."""
    try:
        from config.settings import Settings  # local to avoid circular at module import
    except Exception:
        Settings = None

    if Settings is not None and not getattr(Settings.app, "app_verbose_logging", False):
        app_log("ℹ️ Tab diagnostic skipped (APP_VERBOSE_LOGGING disabled)")
        return

    app_log("🔍 Starting comprehensive tab diagnostic...")

    is_page = hasattr(target, "frames")
    app_log(f"📄 Target type: {'Page' if is_page else 'Frame'}")

    try:
        app_log("📄 Checking main target...")
        main_result = target.evaluate(
            """
            () => {
                const info = {
                    url: window.location.href,
                    title: document.title,
                    frameCount: document.querySelectorAll('iframe').length,
                    bodyText: document.body?.innerText?.substring(0, 200) || 'NO BODY',
                };
                return info;
            }
            """
        )
        app_log(f"  Main info: {main_result}")
    except Exception as e:
        app_log(f"  ❌ Main check failed: {e}")

    if is_page:
        try:
            frames = target.frames
            app_log(f"📦 Total frames found: {len(frames)}")

            for idx, frame in enumerate(frames):
                try:
                    url = frame.url
                    app_log(f"\n🔲 Frame {idx}: {url}")

                    frame_info = frame.evaluate(
                        """
                        () => {
                            const tabs = [];
                            const tabTexts = ['Contents', 'Header', 'Locks', 'LPN Movement', 'Audit', 'Documents'];

                            const allElements = document.querySelectorAll('*');
                            const potentialTabs = [];

                            for (const el of allElements) {
                                const text = (el.textContent || '').trim();

                                for (const tabText of tabTexts) {
                                    if (text === tabText) {
                                        const rect = el.getBoundingClientRect();
                                        const style = window.getComputedStyle(el);

                                        potentialTabs.push({
                                            text: text,
                                            tag: el.tagName,
                                            visible: style.display !== 'none' && style.visibility !== 'hidden',
                                            width: Math.round(rect.width),
                                            height: Math.round(rect.height),
                                        });
                                    }
                                }
                            }

                            return {
                                potentialTabs: potentialTabs,
                                totalElements: allElements.length
                            };
                        }
                        """
                    )

                    if frame_info["potentialTabs"]:
                        app_log(f"  ✅ Found {len(frame_info['potentialTabs'])} potential tabs")
                        for tab in frame_info["potentialTabs"]:
                            app_log(f"    📌 {tab}")

                except Exception as e:
                    app_log(f"  ❌ Frame {idx} check failed: {e}")

        except Exception as e:
            app_log(f"❌ Frame enumeration failed: {e}")
    else:
        app_log("ℹ️ Target is a Frame, skipping frame enumeration")

    app_log("\n✅ Diagnostic complete")


def _click_ilpn_detail_tabs(target):
    """
    Click through all visible iLPN detail tabs sequentially.
    """
    _diagnose_tabs(target)
    target.wait_for_timeout(2000)
    app_log("🎯 Starting tab clicking process...")

    frames_to_try = [target]
    try:
        for frame in target.frames:
            frames_to_try.append(frame)
    except Exception as e:
        app_log(f"⚠️ Could not enumerate frames: {e}")

    tab_names = ["Header", "Contents", "Locks"]

    for tab_name in tab_names:
        app_log(f"\n🔄 Attempting to click tab: {tab_name}")
        clicked = False

        for page_target in frames_to_try:
            if clicked:
                break

            try:
                app_log("  🎯 Trying in frame...")
                try:
                    elements = page_target.get_by_text(tab_name, exact=True)
                    count = elements.count()
                    app_log(f"    Found {count} exact text matches")

                    for i in range(count):
                        try:
                            el = elements.nth(i)
                            el.scroll_into_view_if_needed(timeout=500)
                            el.click(force=True, timeout=1000)
                            app_log(f"    ✅ Clicked element {i}")
                            clicked = True
                            page_target.wait_for_timeout(800)
                            break
                        except Exception as e:
                            app_log(f"    ⚠️ Element {i} click failed: {e}")
                except Exception as e:
                    app_log(f"    ⚠️ Text match strategy failed: {e}")

                if clicked:
                    break

                try:
                    result = page_target.evaluate(
                        """
                        (tabName) => {
                            const allElements = Array.from(document.querySelectorAll('*'));
                            for (const el of allElements) {
                                const text = (el.textContent || '').trim();
                                if (text === tabName) {
                                    try {
                                        el.scrollIntoView({ block: 'center' });
                                        el.click();
                                        return { success: true, tag: el.tagName, text: text };
                                    } catch (e) {
                                        el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                        return { success: true, tag: el.tagName, text: text, method: 'dispatch' };
                                    }
                                }
                            }
                            return { success: false, reason: 'not found' };
                        }
                        """,
                        tab_name,
                    )

                    if result.get("success"):
                        app_log(f"    ✅ JS click succeeded: {result}")
                        clicked = True
                        page_target.wait_for_timeout(800)
                        break
                    else:
                        app_log(f"    ⚠️ JS click failed: {result}")

                except Exception as e:
                    app_log(f"    ⚠️ JS strategy failed: {e}")

            except Exception as e:
                app_log(f"  ❌ Frame attempt failed: {e}")

        if not clicked:
            app_log(f"  ❌ FAILED to click tab: {tab_name}")

    app_log("\n✅ Tab clicking process complete")
    return True


# Backwards compatible aliases for external callers
diagnose_tabs = _diagnose_tabs
click_ilpn_detail_tabs = _click_ilpn_detail_tabs
