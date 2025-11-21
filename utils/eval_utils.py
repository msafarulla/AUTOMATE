"""Safe Playwright evaluate wrappers that handle closed pages gracefully."""

from playwright.sync_api import Page, Locator
from core.logger import app_log


class PageUnavailableError(RuntimeError):
    """Page/context was closed during evaluation."""
    pass


_TRANSIENT_ERRORS = (
    "target closed",
    "execution context was destroyed",
    "cannot find context",
    "page crashed",
    "browser has been closed",
    "frame was detached",
)


def _is_transient(exc: Exception) -> bool:
    """Check if error is due to page/context closing."""
    msg = str(exc).lower()
    return any(e in msg for e in _TRANSIENT_ERRORS)


def safe_page_evaluate(page: Page, script: str, arg=None, 
                       description: str = "evaluate", suppress_log: bool = False):
    """Evaluate script on page, raising PageUnavailableError if page closed."""
    try:
        return page.evaluate(script, arg) if arg else page.evaluate(script)
    except Exception as e:
        if _is_transient(e):
            if not suppress_log:
                app_log(f"⚠️ {description} skipped - page closed")
            raise PageUnavailableError(description) from e
        raise


def safe_locator_evaluate(locator: Locator, script: str,
                          description: str = "evaluate", suppress_log: bool = False):
    """Evaluate script on locator, raising PageUnavailableError if page closed."""
    try:
        return locator.evaluate(script)
    except Exception as e:
        if _is_transient(e):
            if not suppress_log:
                app_log(f"⚠️ {description} skipped - page closed")
            raise PageUnavailableError(description) from e
        raise