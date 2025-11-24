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
) -> bool:
    """Login, open iLPNs, and run the shared filter helper."""
    settings = Settings.from_env()
    success = False

    with create_operation_services(settings) as services:
        try:
            services.stage_actions.run_login()
            services.stage_actions.run_change_warehouse()

            if not services.nav_mgr.open_menu_item(search_term, match_text):
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
        input("Press Enter to exit...")

    return success


def main():
    parser = argparse.ArgumentParser(description="Open iLPNs UI and filter by iLPN.")
    parser.add_argument("--ilpn", required=True, help="iLPN value to filter by")
    parser.add_argument("--search-term", default="ILPNS", help="Menu search keyword")
    parser.add_argument("--match-text", default="iLPNs (Distribution)", help="Menu item text to open")
    args = parser.parse_args()

    open_ilpns_and_filter(
        args.ilpn,
        args.search_term,
        args.match_text
    )


if __name__ == "__main__":
    main()
