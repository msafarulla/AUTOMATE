# =============================================================================
# utils/hash_utils.py
# =============================================================================
"""Frame snapshot utilities for detecting screen changes."""

from playwright.sync_api import Frame
from utils.eval_utils import safe_locator_evaluate


class HashUtils:
    """Utilities for taking frame snapshots."""
    
    SETTLE_MS = 350      # Wait for frame to stabilize
    SNAPSHOT_LEN = 175   # Characters to capture

    @staticmethod
    def get_frame_snapshot(frame: Frame, length: int = None) -> str:
        """
        Get text snapshot of frame body.
        
        Used to detect when screen content changes.
        """
        length = length or HashUtils.SNAPSHOT_LEN
        if length <= 0:
            return ""

        # Wait for frame to settle
        try:
            frame.page.wait_for_timeout(HashUtils.SETTLE_MS)
        except Exception:
            pass

        # Get body text
        return safe_locator_evaluate(
            frame.locator("body"),
            f"el => (el.innerText || '').slice(0, {length})",
            description="frame_snapshot",
            suppress_log=True
        )