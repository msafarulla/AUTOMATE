from playwright.sync_api import Frame
from utils.eval_utils import safe_locator_evaluate


class HashUtils:
    # Extra delay to let RF iframe finish swapping contexts before we read its body.
    FRAME_HASH_SETTLE_MS = 350
    FRAME_SNAPSHOT_CHARS = 175

    @staticmethod
    def _wait_for_settle(frame: Frame):
        settle = HashUtils.FRAME_HASH_SETTLE_MS
        if settle:
            try:
                frame.page.wait_for_timeout(settle)
            except Exception:
                pass

    @staticmethod
    def get_frame_snapshot(frame: Frame, length: int | None = None) -> str:
        """Return the first `length` characters of the frame body text."""
        if length is None:
            length = HashUtils.FRAME_SNAPSHOT_CHARS
        if length <= 0:
            return ""
        HashUtils._wait_for_settle(frame)
        script = f"""
        (el => {{
            const text = el.innerText || "";
            return text.slice(0, {length});
        }})
        """
        return safe_locator_evaluate(
            frame.locator("body"),
            script,
            description="HashUtils.get_frame_snapshot",
            suppress_transient_log=True,
        )
