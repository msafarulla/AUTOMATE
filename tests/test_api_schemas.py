"""
Comprehensive tests for API schemas (api/schemas.py).
"""
import pytest
from pydantic import ValidationError
from api.schemas import ReceiveRequest, OperationResponse


class TestReceiveRequest:
    """Test suite for ReceiveRequest schema."""

    def test_valid_receive_request(self):
        """Test creating valid ReceiveRequest."""
        request = ReceiveRequest(
            asn="ASN123456",
            item="ITEM001",
            quantity=10,
            warehouse="LPM"
        )
        assert request.asn == "ASN123456"
        assert request.item == "ITEM001"
        assert request.quantity == 10
        assert request.warehouse == "LPM"

    def test_receive_request_default_warehouse(self):
        """Test ReceiveRequest with default warehouse."""
        request = ReceiveRequest(
            asn="ASN123456",
            item="ITEM001",
            quantity=5
        )
        assert request.warehouse == "LPM"

    def test_receive_request_missing_required_field(self):
        """Test ReceiveRequest with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ReceiveRequest(
                asn="ASN123456",
                quantity=10
                # Missing 'item'
            )
        errors = exc_info.value.errors()
        assert any(e['loc'] == ('item',) for e in errors)

    def test_receive_request_invalid_quantity_type(self):
        """Test ReceiveRequest with invalid quantity type."""
        with pytest.raises(ValidationError):
            ReceiveRequest(
                asn="ASN123456",
                item="ITEM001",
                quantity="not_a_number"
            )

    def test_receive_request_custom_warehouse(self):
        """Test ReceiveRequest with custom warehouse."""
        request = ReceiveRequest(
            asn="ASN999",
            item="CUSTOM_ITEM",
            quantity=100,
            warehouse="CUSTOM_WH"
        )
        assert request.warehouse == "CUSTOM_WH"

    def test_receive_request_zero_quantity(self):
        """Test ReceiveRequest with zero quantity."""
        request = ReceiveRequest(
            asn="ASN123",
            item="ITEM001",
            quantity=0
        )
        assert request.quantity == 0

    def test_receive_request_large_quantity(self):
        """Test ReceiveRequest with large quantity."""
        request = ReceiveRequest(
            asn="ASN123",
            item="ITEM001",
            quantity=999999
        )
        assert request.quantity == 999999

    def test_receive_request_special_characters_in_asn(self):
        """Test ReceiveRequest with special characters in ASN."""
        request = ReceiveRequest(
            asn="ASN-2024-001_TEST",
            item="ITEM001",
            quantity=5
        )
        assert request.asn == "ASN-2024-001_TEST"

    def test_receive_request_dict_conversion(self):
        """Test converting ReceiveRequest to dict."""
        request = ReceiveRequest(
            asn="ASN123",
            item="ITEM001",
            quantity=10,
            warehouse="TEST"
        )
        data = request.model_dump()
        assert data["asn"] == "ASN123"
        assert data["item"] == "ITEM001"
        assert data["quantity"] == 10
        assert data["warehouse"] == "TEST"

    def test_receive_request_json_serialization(self):
        """Test JSON serialization of ReceiveRequest."""
        request = ReceiveRequest(
            asn="ASN123",
            item="ITEM001",
            quantity=10
        )
        json_str = request.model_dump_json()
        assert "ASN123" in json_str
        assert "ITEM001" in json_str


class TestOperationResponse:
    """Test suite for OperationResponse schema."""

    def test_valid_operation_response_success(self):
        """Test creating valid successful OperationResponse."""
        response = OperationResponse(
            success=True,
            message="Operation completed successfully"
        )
        assert response.success is True
        assert response.message == "Operation completed successfully"
        assert response.screenshot_path is None

    def test_valid_operation_response_failure(self):
        """Test creating valid failed OperationResponse."""
        response = OperationResponse(
            success=False,
            message="Operation failed"
        )
        assert response.success is False
        assert response.message == "Operation failed"

    def test_operation_response_with_screenshot(self):
        """Test OperationResponse with screenshot path."""
        response = OperationResponse(
            success=True,
            message="Completed",
            screenshot_path="/screenshots/test_001.png"
        )
        assert response.screenshot_path == "/screenshots/test_001.png"

    def test_operation_response_missing_required_field(self):
        """Test OperationResponse with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            OperationResponse(
                success=True
                # Missing 'message'
            )
        errors = exc_info.value.errors()
        assert any(e['loc'] == ('message',) for e in errors)

    def test_operation_response_invalid_success_type(self):
        """Test OperationResponse with invalid success type."""
        with pytest.raises(ValidationError):
            OperationResponse(
                success="yes",  # Should be bool
                message="Test"
            )

    def test_operation_response_empty_message(self):
        """Test OperationResponse with empty message."""
        response = OperationResponse(
            success=True,
            message=""
        )
        assert response.message == ""

    def test_operation_response_long_message(self):
        """Test OperationResponse with very long message."""
        long_message = "x" * 10000
        response = OperationResponse(
            success=False,
            message=long_message
        )
        assert len(response.message) == 10000

    def test_operation_response_dict_conversion(self):
        """Test converting OperationResponse to dict."""
        response = OperationResponse(
            success=True,
            message="Success",
            screenshot_path="/path/to/screenshot.png"
        )
        data = response.model_dump()
        assert data["success"] is True
        assert data["message"] == "Success"
        assert data["screenshot_path"] == "/path/to/screenshot.png"

    def test_operation_response_json_serialization(self):
        """Test JSON serialization of OperationResponse."""
        response = OperationResponse(
            success=True,
            message="Test message"
        )
        json_str = response.model_dump_json()
        assert "true" in json_str.lower()
        assert "Test message" in json_str

    def test_operation_response_null_screenshot_path(self):
        """Test OperationResponse with explicitly null screenshot path."""
        response = OperationResponse(
            success=True,
            message="Done",
            screenshot_path=None
        )
        assert response.screenshot_path is None


@pytest.mark.parametrize("asn,item,quantity", [
    ("ASN001", "ITEM001", 1),
    ("ASN999", "ITEM999", 999),
    ("A" * 100, "I" * 100, 1000000),
])
class TestReceiveRequestParametrized:
    """Parametrized tests for ReceiveRequest."""

    def test_various_valid_inputs(self, asn, item, quantity):
        """Test ReceiveRequest with various valid inputs."""
        request = ReceiveRequest(
            asn=asn,
            item=item,
            quantity=quantity
        )
        assert request.asn == asn
        assert request.item == item
        assert request.quantity == quantity


@pytest.mark.parametrize("success,message", [
    (True, "Success"),
    (False, "Failure"),
    (True, ""),
    (False, "Error: Something went wrong"),
])
class TestOperationResponseParametrized:
    """Parametrized tests for OperationResponse."""

    def test_various_responses(self, success, message):
        """Test OperationResponse with various combinations."""
        response = OperationResponse(
            success=success,
            message=message
        )
        assert response.success == success
        assert response.message == message
