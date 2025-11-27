# =============================================================================
# utils/hash_utils.py
# =============================================================================
"""Frame snapshot utilities for detecting screen changes."""

import time
from hashlib import sha256
from playwright.sync_api import Frame
from utils.eval_utils import safe_locator_evaluate


class HashUtils:
    """Utilities for taking frame snapshots."""
    
    SETTLE_MS = 350      # Wait for frame to stabilize
    SNAPSHOT_LEN = 175   # Characters to capture (kept for compatibility)

    @staticmethod
    def get_frame_snapshot(frame: Frame, length: int | None = None) -> str:
        """
        Get text snapshot of frame body.
        
        Used to detect when screen content changes.
        """
        # Wait for frame to settle
        try:
            time.sleep(HashUtils.SETTLE_MS / 1000)
        except Exception:
            pass

        # Get body text (full by default; allow optional truncation if length provided)
        slice_expr = "" if (length is None) else f".slice(0, {max(0, length)})"
        text = safe_locator_evaluate(
            frame.locator("body"),
            f"el => (el.innerText || ''){slice_expr}",
            description="frame_snapshot",
            suppress_log=True,
        )
        # Return sha256 digest of the captured text for stable comparisons.
        return sha256(text.encode("utf-8", errors="ignore")).hexdigest()
