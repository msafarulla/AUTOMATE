"""
Comprehensive tests for data models (models/data_models.py).
"""
import pytest
from dataclasses import asdict
from models.data_models import ASN, Item, OperationResult


class TestASN:
    """Test suite for ASN dataclass."""

    def test_asn_creation(self):
        """Test creating an ASN instance."""
        items = [Item("ITEM001", "Test Item", 10)]
        asn = ASN(
            asn_number="ASN123456",
            warehouse="LPM",
            items=items
        )

        assert asn.asn_number == "ASN123456"
        assert asn.warehouse == "LPM"
        assert len(asn.items) == 1
        assert asn.items[0].item_id == "ITEM001"

    def test_asn_empty_items(self):
        """Test ASN with empty items list."""
        asn = ASN(
            asn_number="ASN123",
            warehouse="TEST",
            items=[]
        )

        assert asn.items == []
        assert len(asn.items) == 0

    def test_asn_multiple_items(self):
        """Test ASN with multiple items."""
        items = [
            Item("ITEM001", "Item 1", 10),
            Item("ITEM002", "Item 2", 20),
            Item("ITEM003", "Item 3", 30),
        ]
        asn = ASN(
            asn_number="ASN999",
            warehouse="WH1",
            items=items
        )

        assert len(asn.items) == 3
        assert asn.items[1].quantity == 20

    def test_asn_dict_conversion(self):
        """Test converting ASN to dict."""
        items = [Item("ITEM001", "Test", 5)]
        asn = ASN("ASN123", "LPM", items)

        asn_dict = asdict(asn)

        assert asn_dict["asn_number"] == "ASN123"
        assert asn_dict["warehouse"] == "LPM"
        assert len(asn_dict["items"]) == 1

    def test_asn_equality(self):
        """Test ASN equality comparison."""
        items1 = [Item("ITEM001", "Test", 10)]
        items2 = [Item("ITEM001", "Test", 10)]

        asn1 = ASN("ASN123", "LPM", items1)
        asn2 = ASN("ASN123", "LPM", items2)

        assert asn1 == asn2

    def test_asn_inequality(self):
        """Test ASN inequality."""
        items = [Item("ITEM001", "Test", 10)]

        asn1 = ASN("ASN123", "LPM", items)
        asn2 = ASN("ASN456", "LPM", items)

        assert asn1 != asn2

    def test_asn_repr(self):
        """Test ASN string representation."""
        items = [Item("ITEM001", "Test", 10)]
        asn = ASN("ASN123", "LPM", items)

        repr_str = repr(asn)

        assert "ASN123" in repr_str
        assert "LPM" in repr_str

    def test_asn_with_special_characters(self):
        """Test ASN with special characters in fields."""
        items = [Item("ITEM-001_TEST", "Test Item #1", 10)]
        asn = ASN(
            asn_number="ASN-2024-001",
            warehouse="WH_TEST",
            items=items
        )

        assert asn.asn_number == "ASN-2024-001"
        assert asn.warehouse == "WH_TEST"


class TestItem:
    """Test suite for Item dataclass."""

    def test_item_creation_with_location(self):
        """Test creating an Item with location."""
        item = Item(
            item_id="ITEM001",
            description="Test Item",
            quantity=10,
            location="A-01-01"
        )

        assert item.item_id == "ITEM001"
        assert item.description == "Test Item"
        assert item.quantity == 10
        assert item.location == "A-01-01"

    def test_item_creation_without_location(self):
        """Test creating an Item without location (default None)."""
        item = Item(
            item_id="ITEM002",
            description="No Location Item",
            quantity=5
        )

        assert item.location is None

    def test_item_zero_quantity(self):
        """Test Item with zero quantity."""
        item = Item("ITEM001", "Zero Qty", 0)
        assert item.quantity == 0

    def test_item_large_quantity(self):
        """Test Item with large quantity."""
        item = Item("ITEM001", "Large Qty", 999999)
        assert item.quantity == 999999

    def test_item_dict_conversion(self):
        """Test converting Item to dict."""
        item = Item("ITEM001", "Test", 10, "A-01-01")

        item_dict = asdict(item)

        assert item_dict["item_id"] == "ITEM001"
        assert item_dict["description"] == "Test"
        assert item_dict["quantity"] == 10
        assert item_dict["location"] == "A-01-01"

    def test_item_equality(self):
        """Test Item equality."""
        item1 = Item("ITEM001", "Test", 10, "A-01")
        item2 = Item("ITEM001", "Test", 10, "A-01")

        assert item1 == item2

    def test_item_inequality_different_id(self):
        """Test Item inequality with different IDs."""
        item1 = Item("ITEM001", "Test", 10)
        item2 = Item("ITEM002", "Test", 10)

        assert item1 != item2

    def test_item_inequality_different_quantity(self):
        """Test Item inequality with different quantities."""
        item1 = Item("ITEM001", "Test", 10)
        item2 = Item("ITEM001", "Test", 20)

        assert item1 != item2

    def test_item_long_description(self):
        """Test Item with very long description."""
        long_desc = "A" * 1000
        item = Item("ITEM001", long_desc, 5)

        assert len(item.description) == 1000

    def test_item_special_characters_in_description(self):
        """Test Item with special characters."""
        item = Item(
            "ITEM-001",
            "Test Item #1 (Special: $100)",
            10,
            "LOC-A/01"
        )

        assert "$100" in item.description
        assert "/" in item.location


class TestOperationResult:
    """Test suite for OperationResult dataclass."""

    def test_operation_result_success(self):
        """Test creating successful OperationResult."""
        result = OperationResult(
            success=True,
            message="Operation completed successfully"
        )

        assert result.success is True
        assert result.message == "Operation completed successfully"
        assert result.data is None

    def test_operation_result_failure(self):
        """Test creating failed OperationResult."""
        result = OperationResult(
            success=False,
            message="Operation failed: Invalid input"
        )

        assert result.success is False
        assert "Invalid input" in result.message

    def test_operation_result_with_data(self):
        """Test OperationResult with additional data."""
        data = {
            "items_processed": 10,
            "timestamp": "2024-01-01T12:00:00",
            "user": "testuser"
        }
        result = OperationResult(
            success=True,
            message="Completed",
            data=data
        )

        assert result.data is not None
        assert result.data["items_processed"] == 10
        assert result.data["user"] == "testuser"

    def test_operation_result_empty_message(self):
        """Test OperationResult with empty message."""
        result = OperationResult(success=True, message="")
        assert result.message == ""

    def test_operation_result_dict_conversion(self):
        """Test converting OperationResult to dict."""
        result = OperationResult(
            success=True,
            message="Success",
            data={"key": "value"}
        )

        result_dict = asdict(result)

        assert result_dict["success"] is True
        assert result_dict["message"] == "Success"
        assert result_dict["data"]["key"] == "value"

    def test_operation_result_equality(self):
        """Test OperationResult equality."""
        result1 = OperationResult(True, "Success", {"key": "value"})
        result2 = OperationResult(True, "Success", {"key": "value"})

        assert result1 == result2

    def test_operation_result_inequality(self):
        """Test OperationResult inequality."""
        result1 = OperationResult(True, "Success")
        result2 = OperationResult(False, "Failure")

        assert result1 != result2

    def test_operation_result_repr(self):
        """Test OperationResult string representation."""
        result = OperationResult(True, "Test message")

        repr_str = repr(result)

        assert "True" in repr_str
        assert "Test message" in repr_str

    def test_operation_result_complex_data(self):
        """Test OperationResult with complex nested data."""
        data = {
            "items": [
                {"id": 1, "name": "Item1"},
                {"id": 2, "name": "Item2"}
            ],
            "metadata": {
                "count": 2,
                "warehouse": "LPM"
            }
        }
        result = OperationResult(True, "Processed items", data)

        assert len(result.data["items"]) == 2
        assert result.data["metadata"]["count"] == 2


@pytest.mark.parametrize("asn_number,warehouse,item_count", [
    ("ASN001", "LPM", 1),
    ("ASN999", "TEST", 5),
    ("ASN-2024-001", "WH_MAIN", 10),
])
class TestASNParametrized:
    """Parametrized tests for ASN."""

    def test_asn_with_various_items(self, asn_number, warehouse, item_count):
        """Test ASN with various item counts."""
        items = [
            Item(f"ITEM{i:03d}", f"Description {i}", i)
            for i in range(1, item_count + 1)
        ]
        asn = ASN(asn_number, warehouse, items)

        assert asn.asn_number == asn_number
        assert asn.warehouse == warehouse
        assert len(asn.items) == item_count


@pytest.mark.parametrize("success,has_data", [
    (True, True),
    (True, False),
    (False, True),
    (False, False),
])
class TestOperationResultParametrized:
    """Parametrized tests for OperationResult."""

    def test_operation_result_combinations(self, success, has_data):
        """Test OperationResult with various combinations."""
        data = {"test": "data"} if has_data else None
        result = OperationResult(success, "Test message", data)

        assert result.success == success
        if has_data:
            assert result.data is not None
        else:
            assert result.data is None
