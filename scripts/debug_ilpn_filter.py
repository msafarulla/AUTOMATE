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
    for frame in page.frames:
        try:
            url = frame.url or ""
        except Exception:
            url = ""
        if "LPNListInbound" in url or "lpn" in url.lower():
            return frame
    return None


def _fill_ilpn_filter(page, ilpn: str) -> bool:
    """Reuse the receive flow filter logic to populate the iLPN quick filter."""
    target_frame = _find_ilpn_frame(page)
    target = target_frame or page
    if not target_frame:
        rf_log("⚠️ Could not locate dedicated iLPNs frame, using active page as fallback.")

    candidates = [
        "//span[contains(translate(normalize-space(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'quick filter')]/following::input[1]",
        "//label[contains(translate(normalize-space(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'lpn')]/following::input[1]",
        "//input[contains(@placeholder,'ilter') and not(@type='hidden')]",
        "//input[contains(@aria-label,'Quick filter') and not(@type='hidden')]",
        "//input[contains(@name,'lpn') and not(@type='hidden')]",
        "//input[contains(@id,'lpn') and not(@type='hidden')]",
        "//input[contains(@name,'filter') and not(@type='hidden')]",
        "input.x-form-text:visible",
        "input[type='text']:visible",
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


def open_ilpns_and_filter(ilpn: str, search_term: str, match_text: str):
    """Login, open iLPNs UI, and try filtering with the provided iLPN."""
    settings = Settings.from_env()
    with create_operation_services(settings) as services:
        services.stage_actions.run_login()
        services.stage_actions.run_change_warehouse()

        if not services.nav_mgr.open_menu_item(search_term, match_text, close_existing=True):
            app_log(f"❌ Could not open menu item '{match_text}'")
            return False

        app_log(f"🔎 Attempting to filter iLPN '{ilpn}'")
        success = _fill_ilpn_filter(services.nav_mgr.page, ilpn)
        if success:
            app_log("✅ iLPN filter interaction completed (check UI for results).")
        else:
            app_log("❌ iLPN filter interaction failed.")
        return success


def main():
    parser = argparse.ArgumentParser(description="Open iLPNs UI and filter by iLPN.")
    parser.add_argument("--ilpn", required=True, help="iLPN value to filter by")
    parser.add_argument("--search-term", default="ILPNS", help="Menu search keyword")
    parser.add_argument("--match-text", default="iLPNs (Distribution)", help="Menu item text to open")
    args = parser.parse_args()

    open_ilpns_and_filter(args.ilpn, args.search_term, args.match_text)


if __name__ == "__main__":
    main()
