# =============================================================================
# utils/hash_utils.py
# =============================================================================
"""Frame snapshot utilities for detecting screen changes."""

import time
from playwright.sync_api import Frame
from utils.eval_utils import safe_locator_evaluate


class HashUtils:
    """Utilities for taking frame snapshots."""

    SETTLE_MS = 350      # Wait for frame to stabilize
    SNAPSHOT_LEN = 175   # Characters to capture (kept for compatibility)

    @staticmethod
    def get_frame_snapshot(frame: Frame, length: int | None = None) -> str:
        """
        Get text snapshot of frame body (first 3 lines, normalized).

        Used to detect when screen content changes.
        Returns normalized text for direct comparison.
        """
        # Wait for frame to settle
        try:
            time.sleep(HashUtils.SETTLE_MS / 1000)
        except Exception:
            pass

        # Get first 3 lines of body text, normalized
        text = safe_locator_evaluate(
            frame.locator("body"),
            """el => {
                const lines = (el.innerText || '').split('\\n');
                const head = lines.slice(0, 3).join(' ');
                return head.replace(/\\s+/g, ' ').trim();
            }""",
            description="frame_snapshot",
            suppress_log=True,
        )
        return text or ""
