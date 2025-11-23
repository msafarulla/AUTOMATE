"""
Debug helper to open the iLPNs UI standalone and exercise the quick filter.

Usage:
    python scripts/debug_ilpn_filter.py --ilpn XYZ123
"""

import argparse
import time
from typing import Optional

from config.settings import Settings
from core.logger import app_log, rf_log
from operations import create_operation_services


def _find_ilpn_frame(page):
    """
    Locate the frame that hosts the iLPNs grid.

    The grid is often inside an inner "uxiframe-*-frame" inside the LPNListInboundMain page,
    so we prefer the deepest non-blank frame whose URL contains 'uxiframe' or 'lpn'.
    """
    app_log("🔍 Scanning frames for iLPN content...")

    def score(frame) -> tuple[int, int]:
        try:
            url = frame.url or ""
        except Exception:
            url = ""
        url_l = url.lower()
        # Higher score for more specific matches
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

    import re
    m = re.search(r"of\s+(\d+)", text or "", re.I)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def _dom_open_ilpn_row(target, ilpn: str) -> bool:
    """DOM fallback: search nested uxiframe tables for the ILPN and open it."""
    try:
        result = target.evaluate(
            """
            (ilpn) => {
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                const digits = (s) => (s || '').replace(/\\D+/g, '');
                const containsIlpn = (txt) => {
                    const t = norm(txt);
                    if (!t) return false;
                    return t.includes(ilpn) || digits(t).includes(digits(ilpn));
                };

                const frames = Array.from(document.querySelectorAll('iframe'));
                const uxiframe =
                    frames.find(f => (f.id || '').includes('uxiframe')) ||
                    frames.find(f => (f.src || '').toLowerCase().includes('uxiframe')) ||
                    frames.find(f => (f.src || '').toLowerCase().includes('lpn')) ||
                    frames[0] ||
                    null;

                const doc = uxiframe?.contentDocument || document;
                if (!doc) return { ok: false, reason: 'no_doc' };

                const tables = Array.from(doc.querySelectorAll('table'));
                let hit = null;

                tables.forEach((tbl, tIdx) => {
                    const rows = Array.from(tbl.querySelectorAll('tr'));
                    rows.some((row, rIdx) => {
                        const txt = norm(row.innerText);
                        if (containsIlpn(txt)) {
                            hit = {
                                tableIdx: tIdx,
                                rowIdx: rIdx,
                                text: txt.slice(0, 200),
                                iframeId: uxiframe?.id || null,
                                iframeSrc: uxiframe?.src || null
                            };
                            const targetEl = row.querySelector('a, button') || row;
                            try { targetEl.scrollIntoView({ block: 'center' }); } catch (e) {}
                            try { targetEl.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 1 })); } catch (e) {}
                            try { targetEl.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, detail: 2 })); } catch (e) {}
                            return true;
                        }
                        return false;
                    });
                });

                if (hit) return { ok: true, ...hit };
                return {
                    ok: false,
                    reason: 'no_match',
                    iframeId: uxiframe?.id || null,
                    iframeSrc: uxiframe?.src || null,
                    tables: tables.length
                };
            }
            """,
            ilpn,
        )
    except Exception as exc:
        rf_log(f"❌ DOM iLPN search failed: {exc}")
        return False

    if result and result.get("ok"):
        tbl = result.get("tableIdx")
        row = result.get("rowIdx")
        app_log(
            f"✅ Opened iLPN row via DOM fallback (table#{tbl} row#{row}, iframe={result.get('iframeId')})"
        )
        return True

    rf_log(
        f"❌ DOM iLPN search found no match "
        f"(iframe={result.get('iframeId') if result else 'n/a'}, tables={result.get('tables') if result else 'n/a'})"
    )
    return False


def _open_single_filtered_ilpn_row(target, ilpn: str) -> bool:
    """Open the single filtered iLPN row (if exactly one is present)."""
    app_log("🔍 Waiting for filtered iLPN results...")
    _wait_for_ext_mask(target, timeout_ms=8000)

    selectors = [
        "div.x-grid-view:visible",
        "div[class*='x-grid-view']:visible",
        "//div[contains(@class,'x-grid-view') and not(contains(@class,'x-hide'))]",
        "table.x-grid-table:visible",
    ]

    rows_locator = None
    row_count = 0
    for attempt in range(12):
        # Prefer ExtJS store count when available
        ext_count = _ext_store_count(target)
        if isinstance(ext_count, int):
            row_count = ext_count
        else:
            row_count = 0

        status_count = _statusbar_count(target)
        if isinstance(status_count, int) and status_count > row_count:
            row_count = status_count

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
                break

        if row_count == 1:
            break
        if row_count > 1:
            app_log(f"ℹ️ Filter shows {row_count} rows; waiting for single result...")
        target.wait_for_timeout(600)

    # Try ExtJS-native open first when we detect a single row
    if row_count == 1 and _ext_open_first_row(target):
        app_log("✅ Opened single iLPN row via ExtJS API")
        return True

    # DOM fallback inside nested uxiframe/table
    if _dom_open_ilpn_row(target, ilpn):
        return True

    # Final attempt using raw locators if we did count rows
    if row_count == 1 and rows_locator:
        row = rows_locator.first
        try:
            row.scroll_into_view_if_needed(timeout=1000)
        except Exception:
            pass

        try:
            row.click(timeout=1500)
        except Exception as exc:
            app_log(f"➖ Row click warning: {exc}")

        open_attempts = [
            lambda: row.dblclick(timeout=1200),
            lambda: row.press("Enter"),
            lambda: row.press("Space"),
            lambda: target.keyboard.press("Enter"),
        ]

        for attempt in open_attempts:
            try:
                attempt()
                app_log("✅ Opened single iLPN row to view details")
                return True
            except Exception as exc:
                app_log(f"➖ Row open attempt did not succeed: {exc}")
                continue

    rf_log(f"❌ Unable to open the filtered iLPN row (row_count={row_count})")
    return False


def _fill_ilpn_filter(page, ilpn: str) -> bool:
    """Reuse the receive flow filter logic to populate the iLPN quick filter and open the result."""
    target_frame = _find_ilpn_frame(page)
    target = target_frame or page
    if not target_frame:
        rf_log("⚠️ Could not locate dedicated iLPNs frame, using active page as fallback.")

    filter_triggered = False
    candidates = [
        # "//span[contains(translate(normalize-space(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'quick filter')]/following::input[1]",
        # "//label[contains(translate(normalize-space(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'lpn')]/following::input[1]",
        # "//input[contains(@placeholder,'ilter') and not(@type='hidden')]",
        # "//input[contains(@aria-label,'Quick filter') and not(@type='hidden')]",
        # "//input[contains(@name,'lpn') and not(@type='hidden')]",
        # "//input[contains(@id,'lpn') and not(@type='hidden')]",
        "//input[contains(@name,'filter') and not(@type='hidden')]",
        "input.x-form-text:visible",
        "input[type='text']:visible",
    ]
    input_field = None
    for sel in candidates:
        app_log(f"🔎 Trying selector: {sel}")
        try:
            locator = target.locator(sel).first
            locator.wait_for(state="visible", timeout=3000)
            input_field = locator
            state = locator.evaluate("""
                el => ({
                    display: getComputedStyle(el).display,
                    visibility: getComputedStyle(el).visibility,
                    disabled: el.disabled,
                    readonly: el.readOnly
                })
            """)
            app_log(f"✅ Selector matched: {sel} (state={state})")
            break
        except Exception as exc:
            app_log(f"➖ Selector not usable: {sel} ({exc})")
            continue

    if not input_field:
        rf_log("⚠️ Could not locate visible iLPN quick filter input, attempting hidden-fill fallback.")
        filter_triggered = False
        try:
            filled = target.evaluate(
                """
                (ilpn) => {
                    const val = String(ilpn);
                    const inputs = Array.from(document.querySelectorAll('input'));
                    if (!inputs.length) return false;
                    console.log('debug_ilpn_filter: found inputs', inputs.length);

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
                        .map(el => ({
                            el,
                            s: score(el),
                            name: el.name,
                            id: el.id,
                            placeholder: el.placeholder,
                            aria: el.getAttribute('aria-label'),
                            type: el.type,
                            display: getComputedStyle(el).display,
                            visibility: getComputedStyle(el).visibility
                        }))
                        .filter(entry => entry.s > 0)
                        .sort((a, b) => b.s - a.s);

                    if (!ranked.length) {
                        console.log('debug_ilpn_filter: no scored inputs');
                        return false;
                    }

                    console.log('debug_ilpn_filter: top candidates', ranked.slice(0, 3));

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

    # Keyboard fallback: Tab twice to focus quick filter, type, press Enter then Space for safety
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

    return _open_single_filtered_ilpn_row(target, ilpn)


def open_ilpns_and_filter(
    ilpn: str,
    search_term: str,
    match_text: str,
    wait: bool,
    hold_seconds: int,
    keep_open: bool,
    close_existing: bool,
):
    """Login, open iLPNs UI, and try filtering with the provided iLPN."""
    settings = Settings.from_env()
    success = False
    with create_operation_services(settings) as services:
        try:
            services.stage_actions.run_login()
            services.stage_actions.run_change_warehouse()

            if not services.nav_mgr.open_menu_item(search_term, match_text, close_existing=close_existing):
                app_log(f"❌ Could not open menu item '{match_text}'")
                success = False
            else:
                app_log(f"🔎 Attempting to filter iLPN '{ilpn}'")
                success = _fill_ilpn_filter(services.nav_mgr.page, ilpn)
                if success:
                    app_log("✅ iLPN filter interaction completed (check UI for results).")
                else:
                    app_log("❌ iLPN filter interaction failed.")
        except Exception as exc:
            app_log(f"❌ Debug run failed: {exc}")
            success = False
        finally:
            if hold_seconds > 0:
                app_log(f"⏸️ Holding browser open for {hold_seconds}s (Ctrl+C to exit sooner). No close buttons will be clicked.")
                try:
                    services.nav_mgr.page.wait_for_timeout(hold_seconds * 1000)
                except KeyboardInterrupt:
                    app_log("⏹️ Hold interrupted by user.")

            if wait:
                app_log("⏸️ Leaving browser open. Press Enter to close and exit.")
                try:
                    input()
                except KeyboardInterrupt:
                    pass

            if keep_open:
                app_log("⏳ Keeping browser session open until Ctrl+C (no auto-close).")
                try:
                    while True:
                        services.nav_mgr.page.wait_for_timeout(5000)
                except KeyboardInterrupt:
                    app_log("⏹️ Keep-open interrupted by user.")

        return success


def main():
    parser = argparse.ArgumentParser(description="Open iLPNs UI and filter by iLPN.")
    parser.add_argument("--ilpn", required=True, help="iLPN value to filter by")
    parser.add_argument("--search-term", default="ILPNS", help="Menu search keyword")
    parser.add_argument("--match-text", default="iLPNs (Distribution)", help="Menu item text to open")
    parser.add_argument("--wait", action="store_true", help="Keep the window open until Enter is pressed")
    parser.add_argument("--hold-seconds", type=int, default=0, help="Keep UI open for N seconds (non-interactive environments)")
    parser.add_argument("--keep-open", action="store_true", help="Keep browser session alive until Ctrl+C (overrides hold/wait timing)")
    parser.add_argument("--keep-existing", action="store_true", help="Do not close existing windows when opening the iLPNs menu")
    args = parser.parse_args()

    if not args.wait and args.hold_seconds == 0 and not args.keep_open:
        app_log("ℹ️ Tip: add --hold-seconds 300 or --keep-open to inspect the UI; otherwise the session will close after filtering.")

    open_ilpns_and_filter(
        args.ilpn,
        args.search_term,
        args.match_text,
        args.wait,
        args.hold_seconds,
        args.keep_open,
        close_existing=not args.keep_existing,
    )


if __name__ == "__main__":
    main()
