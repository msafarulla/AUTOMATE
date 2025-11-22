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
    # Prefer the current main page URL (already authenticated), fallback to configured base_url.
    try:
        if main_page and main_page.url and "about:blank" not in main_page.url and "chrome-error" not in main_page.url:
            source_url = main_page.url
    except Exception:
        source_url = None

    if not source_url and settings and getattr(settings, "app", None):
        source_url = getattr(settings.app, "base_url", None)

    if not source_url or source_url.startswith("about:blank") or "chrome-error" in source_url:
        return False

    try:
        detour_page.goto(source_url, wait_until="networkidle", timeout=20000)
        # Give ExtJS a moment to hydrate before we start querying menus.
        detour_page.wait_for_timeout(500)
        if settings and getattr(settings, "app", None) and getattr(settings.app, "change_warehouse", None):
            try:
                NavigationManager(detour_page, screenshot_mgr).change_warehouse(settings.app.change_warehouse)
            except Exception:
                pass
        return True
    except Exception:
        return False
