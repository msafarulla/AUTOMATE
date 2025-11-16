from playwright.sync_api import Page, Frame
from utils.eval_utils import safe_page_evaluate, safe_locator_evaluate


class HashUtils:
    # Extra delay to let RF iframe finish swapping contexts before we read its body.
    FRAME_HASH_SETTLE_MS = 350
    FRAME_SNAPSHOT_CHARS = 75

    @staticmethod
    def _get_frame_body_text(frame: Frame) -> str:
        settle = HashUtils.FRAME_HASH_SETTLE_MS
        if settle:
            try:
                frame.page.wait_for_timeout(settle)
            except Exception:
                pass

        return safe_locator_evaluate(
            frame.locator("body"),
            "el => el.innerText",
            description="HashUtils._get_frame_body_text",
            suppress_transient_log=True,
        )

    @staticmethod
    def get_frame_snapshot(frame: Frame, length: int | None = None) -> str:
        """Return the first `length` characters of the frame body text."""
        content = HashUtils._get_frame_body_text(frame)
        if length is None:
            length = HashUtils.FRAME_SNAPSHOT_CHARS
        if length <= 0:
            return ""
        return content[:length]
