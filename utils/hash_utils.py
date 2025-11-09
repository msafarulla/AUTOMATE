import hashlib
from playwright.sync_api import Page, Frame
from utils.eval_utils import safe_page_evaluate, safe_locator_evaluate


class HashUtils:
    # Extra delay to let RF iframe finish swapping contexts before we hash its body.
    FRAME_HASH_SETTLE_MS = 350

    @staticmethod
    def get_page_hash(page: Page) -> str:
        """Compute SHA256 hash of full page content"""
        content = safe_page_evaluate(page, "() => document.documentElement.outerHTML",
                                     description="HashUtils.get_page_hash")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def get_frame_hash(frame: Frame) -> str:
        """Compute SHA256 hash of frame content"""
        settle = HashUtils.FRAME_HASH_SETTLE_MS
        if settle:
            try:
                frame.page.wait_for_timeout(settle)
            except Exception:
                pass

        content = safe_locator_evaluate(
            frame.locator("body"),
            "el => el.innerText",
            description="HashUtils.get_frame_hash",
            suppress_transient_log=True,
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
