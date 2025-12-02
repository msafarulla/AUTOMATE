"""
Tests for ConnectionResetGuard class.
"""
import pytest
from unittest.mock import MagicMock, patch, call

from core.connection_guard import ConnectionResetGuard, ConnectionResetDetected


class TestConnectionResetDetectedException:
    """Tests for ConnectionResetDetected exception."""

    def test_is_runtime_error(self):
        """Test that exception is a RuntimeError."""
        exc = ConnectionResetDetected("test reason")
        assert isinstance(exc, RuntimeError)

    def test_stores_message(self):
        """Test that exception stores the message."""
        exc = ConnectionResetDetected("connection reset")
        assert str(exc) == "connection reset"


class TestConnectionResetGuardInitialization:
    """Tests for ConnectionResetGuard initialization."""

    def test_initializes_with_page(self):
        """Test initialization with page."""
        mock_page = MagicMock()

        guard = ConnectionResetGuard(mock_page)

        assert guard.page is mock_page
        assert guard.screenshot_mgr is None
        assert guard._reason is None

    def test_initializes_with_screenshot_manager(self):
        """Test initialization with screenshot manager."""
        mock_page = MagicMock()
        mock_screenshot_mgr = MagicMock()

        guard = ConnectionResetGuard(mock_page, mock_screenshot_mgr)

        assert guard.screenshot_mgr is mock_screenshot_mgr

    def test_registers_event_handlers(self):
        """Test that event handlers are registered."""
        mock_page = MagicMock()

        guard = ConnectionResetGuard(mock_page)

        # Check that event handlers were registered
        assert mock_page.on.call_count == 3
        mock_page.on.assert_any_call("framenavigated", guard._handle_frame_navigation)
        mock_page.on.assert_any_call("domcontentloaded", guard._handle_page_event)
        mock_page.on.assert_any_call("load", guard._handle_page_event)


class TestEnsureOk:
    """Tests for ensure_ok method."""

    def test_does_nothing_when_no_reason(self):
        """Test does nothing when no reason is set."""
        mock_page = MagicMock()
        guard = ConnectionResetGuard(mock_page)

        # Should not raise
        guard.ensure_ok()

    def test_raises_when_reason_set(self):
        """Test raises ConnectionResetDetected when reason is set."""
        mock_page = MagicMock()
        guard = ConnectionResetGuard(mock_page)
        guard._reason = "test reason"

        with pytest.raises(ConnectionResetDetected, match="test reason"):
            guard.ensure_ok()


class TestGuard:
    """Tests for guard method."""

    def test_executes_function_successfully(self):
        """Test executes function when no error detected."""
        mock_page = MagicMock()
        guard = ConnectionResetGuard(mock_page)

        mock_func = MagicMock(return_value="result")

        result = guard.guard(mock_func, "arg1", kwarg1="value1")

        assert result == "result"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    def test_raises_before_execution_if_reason_set(self):
        """Test raises before executing function if reason already set."""
        mock_page = MagicMock()
        guard = ConnectionResetGuard(mock_page)
        guard._reason = "existing reason"

        mock_func = MagicMock()

        with pytest.raises(ConnectionResetDetected, match="existing reason"):
            guard.guard(mock_func)

        # Function should not have been called
        mock_func.assert_not_called()

    def test_checks_after_execution(self):
        """Test checks for connection reset after function execution."""
        mock_page = MagicMock()
        guard = ConnectionResetGuard(mock_page)

        def func_that_triggers_error():
            # Simulate error being detected during execution
            guard._reason = "error during execution"
            return "result"

        with pytest.raises(ConnectionResetDetected, match="error during execution"):
            guard.guard(func_that_triggers_error)

    def test_checks_even_if_function_raises(self):
        """Test ensures check happens even if function raises."""
        mock_page = MagicMock()
        guard = ConnectionResetGuard(mock_page)

        def failing_func():
            guard._reason = "connection reset"
            raise ValueError("some error")

        # Should raise ConnectionResetDetected, not ValueError
        with pytest.raises(ConnectionResetDetected, match="connection reset"):
            guard.guard(failing_func)


class TestHandleFrameNavigation:
    """Tests for _handle_frame_navigation method."""

    def test_checks_main_frame(self):
        """Test checks frame when it's the main frame."""
        mock_page = MagicMock()
        mock_main_frame = MagicMock()
        mock_page.main_frame = mock_main_frame

        guard = ConnectionResetGuard(mock_page)
        guard._check_frame = MagicMock()

        guard._handle_frame_navigation(mock_main_frame)

        guard._check_frame.assert_called_once_with(mock_main_frame)

    def test_ignores_other_frames(self):
        """Test ignores frames that are not the main frame."""
        mock_page = MagicMock()
        mock_main_frame = MagicMock()
        mock_other_frame = MagicMock()
        mock_page.main_frame = mock_main_frame

        guard = ConnectionResetGuard(mock_page)
        guard._check_frame = MagicMock()

        guard._handle_frame_navigation(mock_other_frame)

        guard._check_frame.assert_not_called()


class TestHandlePageEvent:
    """Tests for _handle_page_event method."""

    def test_checks_main_frame(self):
        """Test checks main frame on page event."""
        mock_page = MagicMock()
        mock_main_frame = MagicMock()
        mock_page.main_frame = mock_main_frame

        guard = ConnectionResetGuard(mock_page)
        guard._check_frame = MagicMock()

        guard._handle_page_event(mock_page)

        guard._check_frame.assert_called_once_with(mock_main_frame)


class TestCheckFrame:
    """Tests for _check_frame method."""

    def test_returns_early_if_reason_already_set(self):
        """Test returns early if reason is already set."""
        mock_page = MagicMock()
        mock_frame = MagicMock()

        guard = ConnectionResetGuard(mock_page)
        guard._reason = "already detected"

        guard._check_frame(mock_frame)

        # Should not call trip again or evaluate
        mock_frame.evaluate.assert_not_called()

    def test_detects_chrome_error_url(self):
        """Test detects chrome error URL."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "chrome-error://chromewebdata/"

        guard = ConnectionResetGuard(mock_page)
        guard._trip = MagicMock()

        guard._check_frame(mock_frame)

        guard._trip.assert_called_once()
        assert "chrome error page loaded" in guard._trip.call_args[0][0]

    def test_detects_connection_reset_in_body_text(self):
        """Test detects 'connection was reset' in body text."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "https://example.com"
        mock_frame.evaluate.return_value = "The connection was reset by the server"

        guard = ConnectionResetGuard(mock_page)
        guard._trip = MagicMock()

        guard._check_frame(mock_frame)

        guard._trip.assert_called_once_with("browser reported the connection was reset")

    def test_detects_err_connection_reset_in_body(self):
        """Test detects 'err_connection_reset' in body text."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "https://example.com"
        mock_frame.evaluate.return_value = "ERR_CONNECTION_RESET"

        guard = ConnectionResetGuard(mock_page)
        guard._trip = MagicMock()

        guard._check_frame(mock_frame)

        guard._trip.assert_called_once_with("browser reported the connection was reset")

    def test_detects_site_cant_be_reached(self):
        """Test detects 'this site can't be reached' in body text."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "https://example.com"
        mock_frame.evaluate.return_value = "This site can't be reached"

        guard = ConnectionResetGuard(mock_page)
        guard._trip = MagicMock()

        guard._check_frame(mock_frame)

        guard._trip.assert_called_once_with("browser reported the connection was reset")

    def test_handles_evaluate_exception(self):
        """Test handles exception during frame evaluation."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "https://example.com"
        mock_frame.evaluate.side_effect = Exception("Evaluation failed")

        guard = ConnectionResetGuard(mock_page)
        guard._trip = MagicMock()

        # Should not raise, just return
        guard._check_frame(mock_frame)

        guard._trip.assert_not_called()

    def test_handles_none_url(self):
        """Test handles None URL gracefully."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = None
        mock_frame.evaluate.return_value = "normal page content"

        guard = ConnectionResetGuard(mock_page)
        guard._trip = MagicMock()

        # Should not trip
        guard._check_frame(mock_frame)

        guard._trip.assert_not_called()

    def test_handles_none_body_text(self):
        """Test handles None body text gracefully."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "https://example.com"
        mock_frame.evaluate.return_value = None

        guard = ConnectionResetGuard(mock_page)
        guard._trip = MagicMock()

        # Should not trip
        guard._check_frame(mock_frame)

        guard._trip.assert_not_called()

    def test_case_insensitive_url_check(self):
        """Test URL check is case insensitive."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "CHROME-ERROR://CHROMEWEBDATA/"

        guard = ConnectionResetGuard(mock_page)
        guard._trip = MagicMock()

        guard._check_frame(mock_frame)

        guard._trip.assert_called_once()

    def test_case_insensitive_keyword_check(self):
        """Test keyword check is case insensitive."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "https://example.com"
        mock_frame.evaluate.return_value = "CONNECTION WAS RESET"

        guard = ConnectionResetGuard(mock_page)
        guard._trip = MagicMock()

        guard._check_frame(mock_frame)

        guard._trip.assert_called_once()


class TestTrip:
    """Tests for _trip method."""

    def test_sets_reason_and_logs(self):
        """Test sets reason and logs message."""
        mock_page = MagicMock()

        guard = ConnectionResetGuard(mock_page)

        with patch('core.connection_guard.app_log') as mock_log:
            guard._trip("test reason")

            assert guard._reason == "test reason"
            mock_log.assert_called_once()
            assert "Connection reset detected" in mock_log.call_args[0][0]

    def test_captures_screenshot_when_manager_available(self):
        """Test captures screenshot when manager is available."""
        mock_page = MagicMock()
        mock_screenshot_mgr = MagicMock()

        guard = ConnectionResetGuard(mock_page, mock_screenshot_mgr)

        with patch('core.connection_guard.app_log'):
            guard._trip("test reason")

            mock_screenshot_mgr.capture.assert_called_once_with(
                mock_page,
                "connection_reset",
                "test reason"
            )

    def test_handles_screenshot_exception(self):
        """Test handles exception during screenshot capture."""
        mock_page = MagicMock()
        mock_screenshot_mgr = MagicMock()
        mock_screenshot_mgr.capture.side_effect = Exception("Screenshot failed")

        guard = ConnectionResetGuard(mock_page, mock_screenshot_mgr)

        with patch('core.connection_guard.app_log'):
            # Should not raise
            guard._trip("test reason")

            assert guard._reason == "test reason"

    def test_does_not_overwrite_existing_reason(self):
        """Test does not overwrite existing reason."""
        mock_page = MagicMock()

        guard = ConnectionResetGuard(mock_page)
        guard._reason = "first reason"

        with patch('core.connection_guard.app_log') as mock_log:
            guard._trip("second reason")

            # Should keep first reason
            assert guard._reason == "first reason"
            # Should not log again
            mock_log.assert_not_called()

    def test_skips_screenshot_when_no_manager(self):
        """Test skips screenshot when no manager available."""
        mock_page = MagicMock()

        guard = ConnectionResetGuard(mock_page, screenshot_mgr=None)

        with patch('core.connection_guard.app_log'):
            # Should not raise
            guard._trip("test reason")

            assert guard._reason == "test reason"


class TestIntegration:
    """Integration tests for ConnectionResetGuard."""

    def test_full_detection_flow_with_chrome_error(self):
        """Test full flow of detecting chrome error page."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "chrome-error://chromewebdata/"
        mock_page.main_frame = mock_frame

        guard = ConnectionResetGuard(mock_page)

        with patch('core.connection_guard.app_log'):
            # Simulate frame navigation event
            guard._handle_frame_navigation(mock_frame)

            # Now ensure_ok should raise
            with pytest.raises(ConnectionResetDetected):
                guard.ensure_ok()

    def test_full_detection_flow_with_keyword(self):
        """Test full flow of detecting error via keyword."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "https://example.com"
        mock_frame.evaluate.return_value = "The connection was reset"
        mock_page.main_frame = mock_frame

        guard = ConnectionResetGuard(mock_page)

        with patch('core.connection_guard.app_log'):
            # Simulate page load event
            guard._handle_page_event(mock_page)

            # Now ensure_ok should raise
            with pytest.raises(ConnectionResetDetected):
                guard.ensure_ok()

    def test_guard_wrapper_catches_error_during_function(self):
        """Test guard wrapper catches error that occurs during function execution."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "https://example.com"
        mock_frame.evaluate.return_value = "normal content"
        mock_page.main_frame = mock_frame

        guard = ConnectionResetGuard(mock_page)

        def function_that_causes_navigation():
            # Simulate navigation to error page during function
            mock_frame.url = "chrome-error://chromewebdata/"
            with patch('core.connection_guard.app_log'):
                guard._handle_frame_navigation(mock_frame)
            return "result"

        with pytest.raises(ConnectionResetDetected):
            guard.guard(function_that_causes_navigation)

    def test_no_false_positives_for_normal_pages(self):
        """Test no false positives for normal pages."""
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "https://example.com"
        mock_frame.evaluate.return_value = "Normal page content without error keywords"
        mock_page.main_frame = mock_frame

        guard = ConnectionResetGuard(mock_page)

        # Check frame multiple times
        guard._check_frame(mock_frame)
        guard._check_frame(mock_frame)

        # Should not raise
        guard.ensure_ok()

        # Should execute function normally
        mock_func = MagicMock(return_value="success")
        result = guard.guard(mock_func)
        assert result == "success"
