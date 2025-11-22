"""
Debug helper to open the iLPNs UI standalone and exercise the quick filter.

Usage:
    python scripts/debug_ilpn_filter.py --ilpn XYZ123
"""

import argparse
from typing import Optional

from config.settings import Settings
from core.logger import app_log, rf_log
from operations import create_operation_services


def _find_ilpn_frame(page):
    """Locate the frame that hosts the iLPNs UI."""
    app_log("🔍 Scanning frames for iLPN content...")
    for frame in page.frames:
        try:
            url = frame.url or ""
        except Exception:
            url = ""
        if "LPNListInbound" in url or "lpn" in url.lower():
            app_log(f"✅ Using frame with url: {url}")
            return frame
        app_log(f"➖ Skipping frame url: {url}")
    return None


def _fill_ilpn_filter(page, ilpn: str) -> bool:
    """Reuse the receive flow filter logic to populate the iLPN quick filter."""
    target_frame = _find_ilpn_frame(page)
    target = target_frame or page
    if not target_frame:
        rf_log("⚠️ Could not locate dedicated iLPNs frame, using active page as fallback.")

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
                return True
        except Exception as exc:
            rf_log(f"❌ Hidden iLPN fill fallback failed: {exc}")
            return False

        rf_log("❌ Hidden iLPN fill fallback did not find a candidate.")
        return False

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
            return True
        except Exception as exc:
            app_log(f"➖ Apply candidate not clickable: {exc}")
            continue

    # Keyboard fallback: Tab twice to focus quick filter, type, press Enter then Space for safety
    try:
        target.press("body", "Tab")
        target.press("body", "Tab")
        target.type("body", ilpn)
        target.press("body", "Enter")
        target.press("body", "Space")
        app_log("⌨️ Used keyboard fallback (Tab Tab Enter Space)")
        return True
    except Exception as exc:
        rf_log(f"❌ Unable to click Apply in iLPNs UI (even with keyboard fallback): {exc}")
        return False


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
