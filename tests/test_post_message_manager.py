"""
Comprehensive tests for operations/post_message.py PostMessageManager class.
"""
import pytest
from unittest.mock import MagicMock, Mock, patch, PropertyMock
from operations.post_message import PostMessageManager


class TestPostMessageManagerInit:
    """Tests for PostMessageManager initialization."""

    def test_init_sets_attributes(self):
        """Test initialization sets all required attributes."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()

        manager = PostMessageManager(mock_page, mock_screenshot)

        assert manager.page is mock_page
        assert manager.screenshot_mgr is mock_screenshot
        assert manager._reset_required is False
        assert manager._last_sent_snapshot is None


class TestHasVisibleTextarea:
    """Tests for _has_visible_textarea method."""

    def test_returns_true_when_textarea_visible(self):
        """Test returns True when visible textarea exists."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_frame.locator.return_value = mock_locator

        manager = PostMessageManager(mock_page, mock_screenshot)
        result = manager._has_visible_textarea(mock_frame)

        assert result is True
        mock_frame.locator.assert_called_once_with("textarea:visible")

    def test_returns_false_when_no_textarea(self):
        """Test returns False when no textarea found."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        mock_frame.locator.return_value = mock_locator

        manager = PostMessageManager(mock_page, mock_screenshot)
        result = manager._has_visible_textarea(mock_frame)

        assert result is False

    def test_returns_false_on_exception(self):
        """Test returns False when exception occurs."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_frame.locator.side_effect = Exception("Test error")

        manager = PostMessageManager(mock_page, mock_screenshot)
        result = manager._has_visible_textarea(mock_frame)

        assert result is False


class TestResolveFrame:
    """Tests for _resolve_frame method."""

    def test_returns_frame_with_textarea_immediately(self):
        """Test returns frame when textarea found immediately."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_main_frame = MagicMock()
        mock_page.frames = [mock_frame]
        mock_page.main_frame = mock_main_frame

        manager = PostMessageManager(mock_page, mock_screenshot)

        with patch.object(manager, '_has_visible_textarea', return_value=True):
            result = manager._resolve_frame(timeout_ms=1000)

        assert result is mock_frame

    def test_returns_main_frame_on_timeout(self):
        """Test returns main frame when no iframe with textarea found."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_main_frame = MagicMock()
        mock_page.frames = []
        mock_page.main_frame = mock_main_frame

        manager = PostMessageManager(mock_page, mock_screenshot)
        result = manager._resolve_frame(timeout_ms=100, poll_interval_ms=50)

        assert result is mock_main_frame


class TestIsErrorResponse:
    """Tests for _is_error_response method."""

    def test_detects_error_marker(self):
        """Test detects error markers in response."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        assert manager._is_error_response("This is an error message") is True
        assert manager._is_error_response("Request failed") is True
        assert manager._is_error_response("Exception occurred") is True
        assert manager._is_error_response("Invalid data") is True

    def test_no_error_in_success_response(self):
        """Test returns False for successful response."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        assert manager._is_error_response("Success") is False
        assert manager._is_error_response("Completed") is False
        assert manager._is_error_response("") is False

    def test_handles_none_response(self):
        """Test handles None response gracefully."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        assert manager._is_error_response(None) is False


class TestIsXmlError:
    """Tests for _is_xml_error method."""

    def test_success_with_zero_codes(self):
        """Test identifies success with zero error codes."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        payload = {
            "error_type": "0",
            "resp_code": "0",
            "exception_details": "",
            "persistent_state": "1",
            "ack_code": "TA",
            "response_type": "confirmation"
        }

        assert manager._is_xml_error(payload) is False

    def test_success_with_empty_codes(self):
        """Test identifies success with empty codes."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        payload = {
            "error_type": "",
            "resp_code": "",
            "exception_details": "",
            "persistent_state": "0",
            "ack_code": "AA",
            "response_type": "accepted"
        }

        assert manager._is_xml_error(payload) is False

    def test_error_with_exception_details(self):
        """Test identifies error when exception details present."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        payload = {
            "error_type": "1",
            "resp_code": "500",
            "exception_details": "Database connection failed",
            "persistent_state": "1",
            "ack_code": "",
            "response_type": ""
        }

        assert manager._is_xml_error(payload) is True

    def test_error_with_bad_resp_code(self):
        """Test identifies error with bad response code and no other success indicators."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        # Error requires: bad codes AND (no ack_ok or response_ok) AND exception or bad persistent
        payload = {
            "error_type": "1",
            "resp_code": "404",
            "exception_details": "",
            "persistent_state": "2",  # Bad persistent state
            "ack_code": "",
            "response_type": "error"  # Non-success response type
        }

        assert manager._is_xml_error(payload) is True

    def test_distribution_order_success(self):
        """Test identifies distribution order success correctly."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        payload = {
            "error_type": "",
            "resp_code": "0",
            "exception_details": "",
            "persistent_state": "1",
            "ack_code": "TA",
            "response_type": "",
            "imported_object_type": "distributionorder"
        }

        assert manager._is_xml_error(payload) is False


class TestFormatResponseSummary:
    """Tests for _format_response_summary method."""

    def test_formats_basic_summary(self):
        """Test formats basic summary without exception."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        payload = {
            "resp_code": "0",
            "error_type": "0",
            "persistent_state": "1",
            "exception_details": ""
        }

        summary = manager._format_response_summary(payload)

        assert "RespCode 0" in summary
        assert "ErrorType 0" in summary
        assert "PersistentState 1" in summary

    def test_formats_summary_with_exception(self):
        """Test formats summary including exception details."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        payload = {
            "resp_code": "500",
            "error_type": "1",
            "persistent_state": "0",
            "exception_details": "Connection timeout"
        }

        summary = manager._format_response_summary(payload)

        assert "RespCode 500" in summary
        assert "Connection timeout" in summary

    def test_formats_summary_with_missing_fields(self):
        """Test formats summary with missing fields."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        payload = {}

        summary = manager._format_response_summary(payload)

        assert "n/a" in summary


class TestInterpretResponse:
    """Tests for _interpret_response method."""

    def test_interprets_xml_response_success(self):
        """Test interprets XML response successfully."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        xml_response = """<?xml version="1.0"?>
<Response>
    <Header>
        <Message_Type>ASN</Message_Type>
        <Internal_Reference_ID>12345</Internal_Reference_ID>
    </Header>
    <Response>
        <Persistent_State>1</Persistent_State>
        <Error_Type>0</Error_Type>
        <Resp_Code>0</Resp_Code>
        <Response_Details>
            <Exception_Details></Exception_Details>
        </Response_Details>
    </Response>
    <Application_Advice>
        <Response_Type>confirmation</Response_Type>
        <Application_Ackg_Code>TA</Application_Ackg_Code>
    </Application_Advice>
</Response>"""

        result = manager._interpret_response(xml_response)

        assert result["raw"] == xml_response
        assert result["is_error"] is False
        assert result["payload"]["message_type"] == "ASN"
        assert result["payload"]["internal_id"] == "12345"
        assert result["payload"]["resp_code"] == "0"

    def test_interprets_non_xml_response(self):
        """Test interprets non-XML response."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        plain_response = "Success: Message processed"

        result = manager._interpret_response(plain_response)

        assert result["raw"] == plain_response
        assert result["summary"] == plain_response
        assert result["payload"] == {}

    def test_interprets_empty_response(self):
        """Test interprets empty response."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        result = manager._interpret_response("")

        assert result["raw"] == ""
        assert result["summary"] == "Empty response"
        assert result["is_error"] is False


class TestFormatXmlForTextarea:
    """Tests for _format_xml_for_textarea method."""

    def test_formats_xml_preserving_structure(self):
        """Test formats XML while preserving structure."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        xml_input = '<?xml version="1.0"?><ASN><ASNID>123</ASNID></ASN>'

        result = manager._format_xml_for_textarea(xml_input)

        assert "<ASN>" in result
        assert "<ASNID>123</ASNID>" in result

    def test_handles_non_xml_input(self):
        """Test handles non-XML input gracefully."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        plain_text = "Not XML content"

        result = manager._format_xml_for_textarea(plain_text)

        assert result == plain_text

    def test_handles_empty_input(self):
        """Test handles empty input."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        result = manager._format_xml_for_textarea("")

        assert result == ""


class TestFormatXmlForOverlay:
    """Tests for _format_xml_for_overlay method."""

    def test_formats_xml_for_display(self):
        """Test formats XML for overlay display."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        xml_input = '<ASN><ASNID>123</ASNID></ASN>'

        result = manager._format_xml_for_overlay(xml_input)

        assert "<ASN>" in result
        assert "123" in result

    def test_returns_empty_for_empty_input(self):
        """Test returns empty string for empty input."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        result = manager._format_xml_for_overlay("")

        assert result == ""

    def test_returns_original_on_parse_error(self):
        """Test returns original text on parse error."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        invalid_xml = "<ASN><ASNID>123</ASNID>"  # Missing closing tag

        result = manager._format_xml_for_overlay(invalid_xml)

        assert result == invalid_xml


class TestMarkResetRequired:
    """Tests for _mark_reset_required method."""

    def test_marks_reset_required(self):
        """Test marks reset as required."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        message = "Test message"
        manager._mark_reset_required(message)

        assert manager._reset_required is True
        assert manager._last_sent_snapshot == "Test message"

    def test_strips_message_whitespace(self):
        """Test strips whitespace from message."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)

        message = "  Test message  \n"
        manager._mark_reset_required(message)

        assert manager._last_sent_snapshot == "Test message"


class TestEnsureResetBeforePost:
    """Tests for _ensure_reset_before_post method."""

    def test_returns_none_when_reset_not_required(self):
        """Test returns None when reset not required."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        manager = PostMessageManager(mock_page, mock_screenshot)
        manager._reset_required = False

        result = manager._ensure_reset_before_post(mock_frame, "test")

        assert result is None

    def test_returns_error_when_same_message_present(self):
        """Test returns error dict when same message still present."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_textarea = MagicMock()
        mock_textarea.input_value.return_value = "previous message"

        manager = PostMessageManager(mock_page, mock_screenshot)
        manager._reset_required = True
        manager._last_sent_snapshot = "previous message"

        with patch.object(manager, '_locate_textarea', return_value=mock_textarea):
            result = manager._ensure_reset_before_post(mock_frame, "new message")

        assert result is not None
        assert result["is_error"] is True
        assert "already sent" in result["summary"]

    def test_clears_reset_flag_when_textarea_changed(self):
        """Test clears reset flag when textarea has different content."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_textarea = MagicMock()
        mock_textarea.input_value.return_value = "new message"

        manager = PostMessageManager(mock_page, mock_screenshot)
        manager._reset_required = True
        manager._last_sent_snapshot = "old message"

        with patch.object(manager, '_locate_textarea', return_value=mock_textarea):
            result = manager._ensure_reset_before_post(mock_frame, "new message")

        assert result is None
        assert manager._reset_required is False
        assert manager._last_sent_snapshot is None


class TestResizeTextareas:
    """Tests for _resize_textareas method."""

    def test_resizes_textareas_without_error(self):
        """Test resizes textareas without raising errors."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()

        manager = PostMessageManager(mock_page, mock_screenshot)

        # Should not raise exception
        manager._resize_textareas(mock_frame)

        mock_frame.evaluate.assert_called_once()

    def test_handles_evaluation_exception(self):
        """Test handles exception during evaluation gracefully."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_frame.evaluate.side_effect = Exception("Evaluation failed")

        manager = PostMessageManager(mock_page, mock_screenshot)

        # Should not raise exception
        manager._resize_textareas(mock_frame)


class TestReleasePostMessageFocus:
    """Tests for _release_post_message_focus method."""

    def test_releases_focus_gracefully(self):
        """Test releases focus without raising errors."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()

        manager = PostMessageManager(mock_page, mock_screenshot)

        # Should not raise exception
        manager._release_post_message_focus(mock_frame)

    def test_handles_exceptions_during_release(self):
        """Test handles exceptions during focus release."""
        mock_page = MagicMock()
        mock_page.keyboard.press.side_effect = Exception("Keyboard error")
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_frame.evaluate.side_effect = Exception("Evaluate error")

        manager = PostMessageManager(mock_page, mock_screenshot)

        # Should not raise exception
        manager._release_post_message_focus(mock_frame)


class TestReadResponse:
    """Tests for _read_response method."""

    def test_reads_response_from_priority_selector(self):
        """Test reads response from priority textarea selector."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.input_value.return_value = "Response text"
        mock_frame.locator.return_value.first = mock_locator

        manager = PostMessageManager(mock_page, mock_screenshot)

        with patch.object(manager, '_resize_textareas'):
            result = manager._read_response(mock_frame)

        assert result == "Response text"

    def test_handles_html_entities_in_response(self):
        """Test handles HTML entities in response."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.input_value.return_value = "&lt;Response&gt;Test&lt;/Response&gt;"
        mock_frame.locator.return_value.first = mock_locator

        manager = PostMessageManager(mock_page, mock_screenshot)

        with patch.object(manager, '_resize_textareas'):
            result = manager._read_response(mock_frame)

        assert "<Response>" in result
        assert "Test" in result

    def test_returns_empty_when_no_response_found(self):
        """Test returns empty string when no response found."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.wait_for.side_effect = Exception("Not found")
        mock_frame.locator.return_value.first = mock_locator

        # Make body return empty
        body_locator = MagicMock()
        body_locator.inner_text.return_value = ""

        def locator_side_effect(selector):
            if selector == "body":
                mock = MagicMock()
                mock.inner_text.return_value = ""
                return mock
            return MagicMock(first=mock_locator)

        mock_frame.locator.side_effect = locator_side_effect

        manager = PostMessageManager(mock_page, mock_screenshot)

        with patch.object(manager, '_resize_textareas'):
            result = manager._read_response(mock_frame)

        assert result == ""


class TestReadPayload:
    """Tests for _read_payload method."""

    def test_reads_payload_from_priority_selector(self):
        """Test reads payload from priority textarea selector."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.input_value.return_value = "<ASN>Test</ASN>"
        mock_frame.locator.return_value.first = mock_locator

        manager = PostMessageManager(mock_page, mock_screenshot)
        result = manager._read_payload(mock_frame)

        assert result == "<ASN>Test</ASN>"

    def test_returns_empty_when_no_payload_found(self):
        """Test returns empty string when no payload found."""
        mock_page = MagicMock()
        mock_screenshot = MagicMock()
        mock_frame = MagicMock()
        mock_locator = MagicMock()
        mock_locator.wait_for.side_effect = Exception("Not found")
        mock_locator.input_value.return_value = ""
        mock_frame.locator.return_value.first = mock_locator

        manager = PostMessageManager(mock_page, mock_screenshot)
        result = manager._read_payload(mock_frame)

        assert result == ""


@pytest.mark.parametrize("response_text,expected_error", [
    ("Success", False),
    ("Error: Connection failed", True),
    ("Failed to process", True),
    ("Exception occurred", True),
    ("Invalid request", True),
    ("Completed successfully", False),
])
def test_error_detection_parametrized(response_text, expected_error):
    """Parametrized test for error detection in responses."""
    mock_page = MagicMock()
    mock_screenshot = MagicMock()
    manager = PostMessageManager(mock_page, mock_screenshot)

    assert manager._is_error_response(response_text) == expected_error
