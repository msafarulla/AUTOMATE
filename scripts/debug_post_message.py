"""
Standalone helper to open the Post Message screen and submit a payload.

Usage:
    python scripts/post_message.py --message "<XML or text>"
    python scripts/post_message.py --message-file path/to/message.xml
"""

import argparse
from pathlib import Path

from config.settings import Settings
from core.logger import app_log
from operations import create_operation_services
from ui.post_message import PostMessageManager


def _load_message(args: argparse.Namespace, settings: Settings) -> str:
    if args.message:
        return args.message
    if args.message_file:
        path = Path(args.message_file)
        return path.read_text(encoding="utf-8")
    return settings.app.post_message_text or ""


def run_post_message(
    message: str,
    keep_existing: bool = True,
    hold_seconds: int = 0,
    wait: bool = False,
    keep_open: bool = True,
) -> bool:
    settings = Settings.from_env()
    if not message:
        app_log("❌ No post message provided (empty payload).")
        return False

    with create_operation_services(settings) as services:
        try:
            services.stage_actions.run_login()
            services.stage_actions.run_change_warehouse()

            opened = services.nav_mgr.open_menu_item(
                "POST",
                "Post Message (Integration)",
                close_existing=not keep_existing,
            )
            if not opened:
                app_log("❌ Could not open Post Message screen.")
                return False

            try:
                services.nav_mgr.maximize_non_rf_windows()
            except Exception:
                pass

            post_mgr = PostMessageManager(services.nav_mgr.page, services.screenshot_mgr)
            success, info = post_mgr.send_message(message)
            app_log(f"Post Message summary: {info.get('summary')}")
            payload_preview = info.get("payload")
            if payload_preview:
                app_log(f"Response payload: {payload_preview}")

            if keep_open:
                input("Press Enter to exit and close the browser...")


def main():
    parser = argparse.ArgumentParser(description="Send a Post Message via UI automation.")
    parser.add_argument("--message", help="Message payload to post (XML or text).")
    parser.add_argument("--message-file", help="Path to a file containing the payload.")
    parser.add_argument(
        "--close-existing",
        action="store_true",
        help="Close existing windows before opening Post Message (default is to leave them open).",
    )
    parser.add_argument("--hold-seconds", type=int, default=0, help="Keep UI open after posting for N seconds.")
    parser.add_argument("--wait", action="store_true", help="Keep window open until Enter is pressed.")
    parser.add_argument("--keep-open", action="store_true", help="Keep session alive until Ctrl+C (overrides hold/wait).")
    args = parser.parse_args()

    settings = Settings.from_env()
    payload = _load_message(args, settings)
    success = run_post_message(
        payload,
        keep_existing=not args.close_existing,
        hold_seconds=args.hold_seconds,
        wait=args.wait,
        keep_open=args.keep_open,
    )
    if not success:
        app_log("⚠️ Post Message completed with errors (see logs above).")


if __name__ == "__main__":
    main()
