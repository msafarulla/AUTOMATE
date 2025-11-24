"""
Minimal CLI to open the iLPNs UI and exercise the reusable quick-filter helper.

Usage:
    python scripts/debug_ilpn_filter.py --ilpn XYZ123
"""

import argparse
import sys
from pathlib import Path
from config.settings import Settings
from core.logger import app_log, rf_log
from operations.runner import create_operation_services
from operations.inbound.ilpn_filter_helper import fill_ilpn_filter

# Ensure project root is on sys.path when run directly from scripts/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def open_ilpns_and_filter(
    ilpn: str,
    search_term: str,
    match_text: str,
    hold_seconds: int,
    keep_open: bool,
    close_existing: bool,
) -> bool:
    """Login, open iLPNs, and run the shared filter helper."""
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
                success = fill_ilpn_filter(
                    services.nav_mgr.page,
                    ilpn,
                    screenshot_mgr=services.screenshot_mgr,
                )
                if success:
                    app_log("✅ iLPN filter interaction completed.")
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
    parser.add_argument("--hold-seconds", type=int, default=0, help="Keep UI open for N seconds (non-interactive environments)")
    parser.add_argument("--keep-open", action="store_true", help="Keep browser session alive until Ctrl+C (overrides hold timing)")
    parser.add_argument("--keep-existing", action="store_true", help="Do not close existing windows when opening the iLPNs menu")
    args = parser.parse_args()

    open_ilpns_and_filter(
        args.ilpn,
        args.search_term,
        args.match_text,
        args.hold_seconds,
        args.keep_open,
        close_existing=not args.keep_existing,
    )


if __name__ == "__main__":
    main()
