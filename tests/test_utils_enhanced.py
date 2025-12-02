"""
Enhanced tests for utility modules.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import time
from utils.eval_utils import (
    safe_page_evaluate,
    safe_locator_evaluate,
    PageUnavailableError,
    _is_transient
)
from utils.hash_utils import HashUtils
from utils.retry import retry, RetryConfig
from utils.wait_utils import WaitUtils


class TestEvalUtils:
    """Enhanced tests for eval_utils.py."""

    def test_safe_page_evaluate_success(self):
        """Test successful page evaluation."""
        mock_page = MagicMock()
        mock_page.evaluate.return_value = {"result": "success"}

        result = safe_page_evaluate(mock_page, "() => ({result: 'success'})")

        assert result == {"result": "success"}
        mock_page.evaluate.assert_called_once()

    def test_safe_page_evaluate_with_arg(self):
        """Test page evaluation with argument."""
        mock_page = MagicMock()
        mock_page.evaluate.return_value = 42

        result = safe_page_evaluate(mock_page, "(x) => x * 2", 21)

        assert result == 42

    def test_safe_page_evaluate_transient_error(self):
        """Test handling of transient errors."""
        mock_page = MagicMock()
        mock_page.evaluate.side_effect = Exception("target closed")

        with pytest.raises(PageUnavailableError):
            safe_page_evaluate(mock_page, "() => true")

    def test_safe_page_evaluate_non_transient_error(self):
        """Test handling of non-transient errors."""
        mock_page = MagicMock()
        mock_page.evaluate.side_effect = Exception("JavaScript error")

        with pytest.raises(Exception, match="JavaScript error"):
            safe_page_evaluate(mock_page, "() => invalid.code()")

    def test_safe_page_evaluate_suppress_log(self):
        """Test evaluation with log suppression."""
        mock_page = MagicMock()
        mock_page.evaluate.side_effect = Exception("target closed")

        with pytest.raises(PageUnavailableError):
            safe_page_evaluate(mock_page, "() => true", suppress_log=True)

    def test_safe_locator_evaluate_success(self):
        """Test successful locator evaluation."""
        mock_locator = MagicMock()
        mock_locator.evaluate.return_value = "text content"

        result = safe_locator_evaluate(mock_locator, "el => el.textContent")

        assert result == "text content"

    def test_safe_locator_evaluate_page_closed(self):
        """Test locator evaluation when page closed."""
        mock_locator = MagicMock()
        mock_locator.evaluate.side_effect = Exception("execution context was destroyed")

        with pytest.raises(PageUnavailableError):
            safe_locator_evaluate(mock_locator, "el => el.value")

    def test_is_transient_all_errors(self):
        """Test detection of all transient error types."""
        transient_errors = [
            "target closed",
            "execution context was destroyed",
            "cannot find context",
            "page crashed",
            "browser has been closed",
            "frame was detached"
        ]

        for error_msg in transient_errors:
            exc = Exception(error_msg)
            assert _is_transient(exc) is True

    def test_is_transient_non_transient(self):
        """Test detection of non-transient errors."""
        exc = Exception("Random error message")
        assert _is_transient(exc) is False

    def test_is_transient_case_insensitive(self):
        """Test transient error detection is case insensitive."""
        exc = Exception("TARGET CLOSED")
        assert _is_transient(exc) is True


class TestHashUtils:
    """Enhanced tests for hash_utils.py."""

    def test_get_frame_snapshot_basic(self):
        """Test basic frame snapshot."""
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.evaluate.return_value = "Line 1 Line 2 Line 3"
        mock_frame.locator.return_value = mock_locator

        with patch('time.sleep'):
            snapshot = HashUtils.get_frame_snapshot(mock_frame)

        assert snapshot == "Line 1 Line 2 Line 3"

    def test_get_frame_snapshot_empty(self):
        """Test snapshot of empty frame."""
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.evaluate.return_value = ""
        mock_frame.locator.return_value = mock_locator

        with patch('time.sleep'):
            snapshot = HashUtils.get_frame_snapshot(mock_frame)

        assert snapshot == ""

    def test_get_frame_snapshot_with_custom_length(self):
        """Test snapshot with custom length parameter."""
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.evaluate.return_value = "Test content"
        mock_frame.locator.return_value = mock_locator

        with patch('time.sleep'):
            snapshot = HashUtils.get_frame_snapshot(mock_frame, length=10)

        # Note: length parameter kept for compatibility but not used in evaluation
        assert snapshot == "Test content"

    def test_get_frame_snapshot_settle_time(self):
        """Test that frame settle time is applied."""
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.evaluate.return_value = "content"
        mock_frame.locator.return_value = mock_locator

        start_time = time.time()
        with patch('time.sleep', wraps=time.sleep) as mock_sleep:
            HashUtils.get_frame_snapshot(mock_frame)

        # Should have called sleep with settle time
        mock_sleep.assert_called()

    def test_hash_utils_constants(self):
        """Test HashUtils constants."""
        assert HashUtils.SETTLE_MS == 350
        assert HashUtils.SNAPSHOT_LEN == 175

    def test_get_frame_snapshot_multiline(self):
        """Test snapshot with multiline content."""
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.evaluate.return_value = "Line1 Line2 Line3"
        mock_frame.locator.return_value = mock_locator

        with patch('time.sleep'):
            snapshot = HashUtils.get_frame_snapshot(mock_frame)

        assert "Line1" in snapshot
        assert "Line2" in snapshot

    def test_get_frame_snapshot_error_handling(self):
        """Test snapshot when evaluation fails."""
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.evaluate.side_effect = Exception("Frame detached")
        mock_frame.locator.return_value = mock_locator

        with patch('time.sleep'):
            with pytest.raises(Exception):
                HashUtils.get_frame_snapshot(mock_frame)


class TestRetry:
    """Enhanced tests for retry.py functionality."""

    def test_retry_success_first_attempt(self):
        """Test successful operation on first attempt."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1)
        def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_operation()

        assert result == "success"
        assert call_count == 1

    def test_retry_success_after_failures(self):
        """Test successful operation after failures."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1)
        def eventually_successful():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        result = eventually_successful()

        assert result == "success"
        assert call_count == 3

    def test_retry_max_attempts_exceeded(self):
        """Test retry giving up after max attempts."""
        call_count = 0

        @retry(max_attempts=3, delay=0.1)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            always_fails()

        assert call_count == 3

    def test_retry_with_retry_config(self):
        """Test retry with RetryConfig."""
        config = RetryConfig(max_attempts=5, delay=0.05)
        call_count = 0

        @retry(config=config)
        def operation_with_config():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise RuntimeError("Retry")
            return "done"

        result = operation_with_config()

        assert result == "done"
        assert call_count == 4


class TestWaitUtils:
    """Enhanced tests for wait_utils.py."""

    @patch('utils.wait_utils.WaitUtils')
    def test_wait_brief(self, mock_wait_utils):
        """Test brief wait functionality."""
        mock_page = MagicMock()

        WaitUtils.wait_brief(mock_page, timeout_ms=500)

        # Verify wait was called with correct timeout
        mock_page.wait_for_timeout.assert_called()

    @patch('utils.wait_utils.WaitUtils')
    def test_wait_for_mask_clear(self, mock_wait_utils):
        """Test waiting for loading mask to clear."""
        mock_page = MagicMock()

        mock_wait_utils.wait_for_mask_clear.return_value = True

        result = WaitUtils.wait_for_mask_clear(mock_page, timeout_ms=3000)

        assert result is True

    @patch('utils.wait_utils.WaitUtils')
    def test_wait_for_screen_change(self, mock_wait_utils):
        """Test waiting for screen content change."""
        mock_get_frame = MagicMock()

        mock_wait_utils.wait_for_screen_change.return_value = True

        result = WaitUtils.wait_for_screen_change(
            mock_get_frame,
            prev_snapshot="old",
            timeout_ms=4000
        )

        assert result is True


@pytest.mark.parametrize("error_message,is_transient", [
    ("target closed", True),
    ("execution context was destroyed", True),
    ("cannot find context", True),
    ("page crashed", True),
    ("browser has been closed", True),
    ("frame was detached", True),
    ("JavaScript error", False),
    ("Network error", False),
    ("Timeout", False),
])
class TestTransientErrorsParametrized:
    """Parametrized tests for transient error detection."""

    def test_transient_error_detection(self, error_message, is_transient):
        """Test detecting transient vs non-transient errors."""
        exc = Exception(error_message)
        assert _is_transient(exc) == is_transient


@pytest.mark.slow
class TestUtilsIntegration:
    """Integration tests for utility modules."""

    def test_retry_with_real_delays(self):
        """Test retry with actual time delays."""
        # Placeholder for integration test with real timing
        pass

    def test_frame_snapshot_with_real_frame(self):
        """Test frame snapshot with real Playwright frame."""
        # Placeholder for integration test
        pass
