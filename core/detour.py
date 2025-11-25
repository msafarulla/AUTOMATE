from typing import Any, Callable

from core.logger import rf_log, app_log
from ui.navigation import NavigationManager


def ensure_detour_page_ready(detour_page, main_page=None, settings=None, screenshot_mgr=None) -> bool:
    """Make sure the detour page is navigated to the app so menu search works."""
    try:
        current = detour_page.url or ""
    except Exception:
        return False

    if current and current != "about:blank" and "chrome-error" not in current:
        return True

    source_url = None
    # Prefer the current main page URL (already authenticated), fallback to configured app_server.
    try:
        if main_page and main_page.url and "about:blank" not in main_page.url and "chrome-error" not in main_page.url:
            source_url = main_page.url
    except Exception:
        source_url = None

    if not source_url and settings and getattr(settings, "app", None):
        source_url = getattr(settings.app, "app_server", None)

    if not source_url or source_url.startswith("about:blank") or "chrome-error" in source_url:
        return False

    try:
        detour_page.goto(source_url, wait_until="networkidle", timeout=20000)
        # Give ExtJS a moment to hydrate before we start querying menus.
        detour_page.wait_for_timeout(500)
        if settings and getattr(settings, "app", None) and getattr(settings.app, "change_warehouse", None):
            try:
                NavigationManager(detour_page, screenshot_mgr).change_warehouse(settings.app.change_warehouse, onDemand=False)
            except Exception:
                pass
        return True
    except Exception:
        return False


def run_open_ui_detours(
    open_ui_cfg: dict[str, Any] | list[dict[str, Any]] | None,
    *,
    main_page,
    screenshot_mgr,
    main_nav: NavigationManager | None = None,
    detour_page=None,
    detour_nav: NavigationManager | None = None,
    settings=None,
    fill_ilpn_cb: Callable[[str, Any], bool] | None = None,
    screen_context: dict | None = None,
) -> bool:
    """
    Open one or more configured UIs mid-flow (e.g., Tasks or iLPNs).
    Returns True if all detours succeed or none requested.
    """
    if not open_ui_cfg:
        return True

    # Normalize to a list of entries
    entries: list[dict[str, Any]] = []
    base_cfg: dict[str, Any] = {}
    if isinstance(open_ui_cfg, list):
        entries = open_ui_cfg
    elif isinstance(open_ui_cfg, dict):
        if not bool(open_ui_cfg.get("enabled", True)):
            return True
        base_cfg = open_ui_cfg
        entries = open_ui_cfg.get("entries") or [open_ui_cfg]
    else:
        return True

    nav_mgr_main = main_nav or (NavigationManager(main_page, screenshot_mgr) if main_page else None)
    detour_nav = detour_nav or (NavigationManager(detour_page, screenshot_mgr) if detour_page else None)

    for idx, entry in enumerate(entries, 1):
        if not entry or not bool(entry.get("enabled", True)):
            continue

        use_nav = detour_nav if detour_nav else nav_mgr_main
        use_page = detour_page if detour_page else main_page
        if not use_nav or not use_page:
            return False

        if detour_page:
            ensure_detour_page_ready(detour_page, main_page, settings, screenshot_mgr)
            try:
                use_nav.close_active_windows(skip_titles=["rf menu"])
            except Exception:
                pass
        else:
            try:
                use_nav.close_active_windows()
            except Exception:
                pass

        search_term = entry.get("search_term") or base_cfg.get("search_term", "tasks")
        match_text = entry.get("match_text") or base_cfg.get("match_text", "Tasks (Configuration)")
        if not use_nav.open_menu_item(search_term, match_text, onDemand=False):
            rf_log(f"❌ UI detour #{idx} failed.")
            return False

        # Expand the detour window for better visibility/capture.
        try:
            use_page.wait_for_timeout(5000)
            use_nav.maximize_non_rf_windows()
        except Exception:
            pass

        operation_note = (
            entry.get("operation_note")
            or base_cfg.get("operation_note")
            or f"Visited UI #{idx} during flow"
        )
        screenshot_tag = (
            entry.get("screenshot_tag")
            or base_cfg.get("screenshot_tag")
            or f"open_ui_{idx}"
        )

        rf_log(f"ℹ️ {operation_note}")

        if entry.get("close_after_open"):
            try:
                windows = use_page.locator("div.x-window:visible")
                if windows.count() > 0:
                    win = windows.last
                    try:
                        win.locator(".x-tool-close").first.click()
                    except Exception:
                        try:
                            use_page.keyboard.press("Escape")
                        except Exception:
                            pass
                NavigationManager(use_page, screenshot_mgr).close_active_windows(skip_titles=[])
            except Exception:
                pass

        if entry.get("fill_ilpn") and fill_ilpn_cb and screen_context and screen_context.get("ilpn"):
            if entry.get("drill_detail") or base_cfg.get("drill_detail"):
                app_log("ℹ️ Attempting to drill into iLPN details and tabs")
            ilpn_val = screen_context.get("ilpn")
            if not fill_ilpn_cb(str(ilpn_val), page=use_page):
                return False
            use_page.wait_for_timeout(5000)
    return True
