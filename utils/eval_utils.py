from playwright.sync_api import Page, Locator


class PageUnavailableError(RuntimeError):
    """Raised when Playwright loses the page/context during an evaluate call."""


_TRANSIENT_MARKERS = (
    "target closed",
    "execution context was destroyed",
    "cannot find context with specified id",
    "page crashed",
    "browser has been closed",
    "frame was detached",
)


def _is_transient_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _TRANSIENT_MARKERS)


def safe_page_evaluate(page: Page, script: str, arg=None, description: str = "page.evaluate",
                       *, suppress_transient_log: bool = False):
    """Wrapper around page.evaluate that normalizes closed-page errors."""
    try:
        if arg is not None:
            return page.evaluate(script, arg)
        return page.evaluate(script)
    except Exception as exc:
        if _is_transient_error(exc):
            if not suppress_transient_log:
                print(f"⚠️ {description} skipped because the page/context closed: {exc}")
            raise PageUnavailableError(description) from exc
        raise


def safe_locator_evaluate(locator: Locator, script: str, description: str = "locator.evaluate",
                          *, suppress_transient_log: bool = False):
    """Wrapper around locator.evaluate with the same transient handling."""
    try:
        return locator.evaluate(script)
    except Exception as exc:
        if _is_transient_error(exc):
            if not suppress_transient_log:
                print(f"⚠️ {description} skipped because the page/context closed: {exc}")
            raise PageUnavailableError(description) from exc
        raise
