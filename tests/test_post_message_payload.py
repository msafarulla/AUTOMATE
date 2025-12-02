"""
Tests for post_message_payload module.
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from core.post_message_payload import (
    build_post_message_payload,
    customize_asn_payload,
    _normalize_msg_type,
    _extract_asn_id,
    _value_case_insensitive,
    _values_have_quantity,
    _set_child_text,
    _extract_quantity_overrides,
    _default_quantity_value,
    _build_receive_items,
    _derive_quantity_for_receive,
    _resolve_tag_case,
    _build_quantity_element,
    _current_timestamp,
)


class TestNormalizeMessageType:
    """Tests for _normalize_msg_type function."""

    def test_normalizes_asn(self):
        """Test ASN normalization."""
        assert _normalize_msg_type("asn") == "ASN"
        assert _normalize_msg_type("ASN") == "ASN"
        assert _normalize_msg_type("  asn  ") == "ASN"

    def test_normalizes_distribution_order(self):
        """Test DistributionOrder normalization."""
        assert _normalize_msg_type("distributionorder") == "DistributionOrder"
        assert _normalize_msg_type("do") == "DistributionOrder"
        assert _normalize_msg_type("order") == "DistributionOrder"
        assert _normalize_msg_type("DO") == "DistributionOrder"

    def test_returns_none_for_invalid_types(self):
        """Test invalid message types return None."""
        assert _normalize_msg_type("invalid") is None
        assert _normalize_msg_type("") is None
        assert _normalize_msg_type(None) is None
        assert _normalize_msg_type("  ") is None


class TestExtractASNId:
    """Tests for _extract_asn_id function."""

    def test_extracts_asn_id_from_valid_xml(self):
        """Test extracting ASN ID from valid XML."""
        xml = """<?xml version="1.0"?>
        <root>
            <ASN>
                <ASNID>12345678</ASNID>
            </ASN>
        </root>"""
        assert _extract_asn_id(xml) == "12345678"

    def test_returns_none_for_invalid_xml(self):
        """Test invalid XML returns None."""
        assert _extract_asn_id("not xml") is None
        assert _extract_asn_id("") is None

    def test_returns_none_when_asn_element_missing(self):
        """Test missing ASN element returns None."""
        xml = """<?xml version="1.0"?><root></root>"""
        assert _extract_asn_id(xml) is None

    def test_returns_none_when_asnid_missing(self):
        """Test missing ASNID returns None."""
        xml = """<?xml version="1.0"?>
        <root>
            <ASN>
                <OtherField>value</OtherField>
            </ASN>
        </root>"""
        assert _extract_asn_id(xml) is None


class TestValueCaseInsensitive:
    """Tests for _value_case_insensitive function."""

    def test_finds_exact_case_match(self):
        """Test finding exact case match."""
        values = {"ItemName": "ABC123", "Quantity": 100}
        assert _value_case_insensitive(values, "ItemName") == "ABC123"

    def test_finds_case_insensitive_match(self):
        """Test case insensitive matching."""
        values = {"ItemName": "ABC123", "quantity": 100}
        assert _value_case_insensitive(values, "itemname") == "ABC123"
        assert _value_case_insensitive(values, "QUANTITY") == 100

    def test_returns_none_when_not_found(self):
        """Test returns None when key not found."""
        values = {"ItemName": "ABC123"}
        assert _value_case_insensitive(values, "NotFound") is None

    def test_handles_empty_dict(self):
        """Test handles empty dictionary."""
        assert _value_case_insensitive({}, "anything") is None


class TestValuesHaveQuantity:
    """Tests for _values_have_quantity function."""

    def test_detects_lowercase_quantity(self):
        """Test detects 'quantity' key."""
        assert _values_have_quantity({"quantity": 100}) is True

    def test_detects_uppercase_quantity(self):
        """Test detects 'Quantity' key."""
        assert _values_have_quantity({"Quantity": 100}) is True

    def test_detects_mixed_case_quantity(self):
        """Test detects 'QuAnTiTy' key."""
        assert _values_have_quantity({"QuAnTiTy": 100}) is True

    def test_returns_false_when_no_quantity(self):
        """Test returns False when no quantity key."""
        assert _values_have_quantity({"ItemName": "ABC"}) is False
        assert _values_have_quantity({}) is False


class TestSetChildText:
    """Tests for _set_child_text function."""

    def test_creates_new_child_when_not_exists(self):
        """Test creates new child element."""
        parent = ET.Element("Parent")
        _set_child_text(parent, "Child", "value")

        assert parent.find("Child") is not None
        assert parent.find("Child").text == "value"

    def test_updates_existing_child(self):
        """Test updates existing child element."""
        parent = ET.Element("Parent")
        child = ET.SubElement(parent, "Child")
        child.text = "old"

        result = _set_child_text(parent, "Child", "new")
        # _set_child_text uses case-insensitive lookup and returns the node
        assert result is not None
        assert result.text == "new"

    def test_returns_none_when_value_is_none(self):
        """Test returns None when value is None."""
        parent = ET.Element("Parent")
        result = _set_child_text(parent, "Child", None)
        assert result is None

    def test_inserts_at_index_when_specified(self):
        """Test inserts at specific index."""
        parent = ET.Element("Parent")
        ET.SubElement(parent, "First")
        ET.SubElement(parent, "Third")

        _set_child_text(parent, "Second", "value", insert_index=1)

        children = list(parent)
        assert len(children) == 3
        assert children[1].tag == "Second"
        assert children[1].text == "value"

    def test_converts_value_to_string(self):
        """Test converts non-string values to string."""
        parent = ET.Element("Parent")
        _set_child_text(parent, "Child", 123)
        assert parent.find("Child").text == "123"


class TestExtractQuantityOverrides:
    """Tests for _extract_quantity_overrides function."""

    def test_extracts_quantity_dict_uppercase(self):
        """Test extracts Quantity dictionary."""
        values = {"Quantity": {"ShippedQty": "100", "ReceivedQty": "50"}}
        result = _extract_quantity_overrides(values)
        assert result == {"shippedqty": "100", "receivedqty": "50"}

    def test_extracts_quantity_dict_lowercase(self):
        """Test extracts quantity dictionary."""
        values = {"quantity": {"shippedqty": "100", "receivedqty": "50"}}
        result = _extract_quantity_overrides(values)
        assert result == {"shippedqty": "100", "receivedqty": "50"}

    def test_returns_empty_dict_when_quantity_not_dict(self):
        """Test returns empty dict when Quantity is not a dict."""
        values = {"Quantity": "100"}
        result = _extract_quantity_overrides(values)
        assert result == {}

    def test_returns_empty_dict_when_no_quantity(self):
        """Test returns empty dict when no Quantity key."""
        values = {"ItemName": "ABC"}
        result = _extract_quantity_overrides(values)
        assert result == {}


class TestDefaultQuantityValue:
    """Tests for _default_quantity_value function."""

    def test_returns_shipped_qty_default(self):
        """Test returns default for shippedqty."""
        assert _default_quantity_value("shippedqty") == "2000"

    def test_returns_received_qty_default(self):
        """Test returns default for receivedqty."""
        assert _default_quantity_value("receivedqty") == "0"

    def test_returns_qty_uom_default(self):
        """Test returns default for qtyuom."""
        assert _default_quantity_value("qtyuom") == "Unit"

    def test_returns_empty_string_for_unknown(self):
        """Test returns empty string for unknown tags."""
        assert _default_quantity_value("unknown") == ""
        assert _default_quantity_value("") == ""


class TestBuildReceiveItems:
    """Tests for _build_receive_items function."""

    def test_builds_items_from_valid_data(self):
        """Test building receive items from valid data."""
        items = [
            {"ItemName": "ITEM1", "Quantity": {"ShippedQty": "100"}},
            {"ItemName": "ITEM2", "Quantity": {"ShippedQty": "200"}},
        ]
        result = _build_receive_items(items)

        assert len(result) == 2
        assert result[0] == {"item": "ITEM1", "quantity": 100}
        assert result[1] == {"item": "ITEM2", "quantity": 200}

    def test_skips_items_without_item_name(self):
        """Test skips items without ItemName."""
        items = [
            {"ItemName": "ITEM1", "Quantity": 100},
            {"Quantity": 100},  # No ItemName
        ]
        result = _build_receive_items(items)
        assert len(result) == 1
        assert result[0]["item"] == "ITEM1"

    def test_skips_none_items(self):
        """Test skips None items."""
        items = [
            {"ItemName": "ITEM1", "Quantity": 100},
            None,
        ]
        result = _build_receive_items(items)
        assert len(result) == 1

    def test_handles_empty_list(self):
        """Test handles empty list."""
        result = _build_receive_items([])
        assert result == []

    def test_uses_item_key_as_fallback(self):
        """Test uses 'item' key as fallback for ItemName."""
        items = [{"item": "ITEM1", "Quantity": 100}]
        result = _build_receive_items(items)
        assert result[0]["item"] == "ITEM1"


class TestDeriveQuantityForReceive:
    """Tests for _derive_quantity_for_receive function."""

    def test_derives_from_shipped_qty_uppercase(self):
        """Test derives from ShippedQty in Quantity dict."""
        item = {"Quantity": {"ShippedQty": "150"}}
        assert _derive_quantity_for_receive(item) == 150

    def test_derives_from_shipped_qty_lowercase(self):
        """Test derives from shippedqty in quantity dict."""
        item = {"quantity": {"shippedqty": "250"}}
        assert _derive_quantity_for_receive(item) == 250

    def test_derives_from_direct_quantity_int(self):
        """Test derives from direct quantity integer."""
        item = {"quantity": 75}
        assert _derive_quantity_for_receive(item) == 75

    def test_derives_from_direct_quantity_string(self):
        """Test derives from direct quantity string."""
        item = {"Quantity": "99"}
        assert _derive_quantity_for_receive(item) == 99

    def test_returns_default_when_no_quantity(self):
        """Test returns default 2000 when no quantity."""
        item = {"ItemName": "ITEM1"}
        assert _derive_quantity_for_receive(item) == 2000

    def test_returns_default_when_quantity_not_parseable(self):
        """Test returns default when quantity not parseable."""
        item = {"quantity": "invalid"}
        assert _derive_quantity_for_receive(item) == 2000


class TestResolveTagCase:
    """Tests for _resolve_tag_case function."""

    def test_finds_exact_case_match(self):
        """Test finds exact case match."""
        parent = ET.Element("Parent")
        child = ET.SubElement(parent, "Quantity")

        result = _resolve_tag_case(parent, "Quantity")
        assert result is child

    def test_finds_case_insensitive_match(self):
        """Test finds case insensitive match."""
        parent = ET.Element("Parent")
        child = ET.SubElement(parent, "Quantity")

        result = _resolve_tag_case(parent, "quantity")
        assert result is child

    def test_returns_none_when_not_found(self):
        """Test returns None when tag not found."""
        parent = ET.Element("Parent")
        result = _resolve_tag_case(parent, "NotFound")
        assert result is None


class TestBuildQuantityElement:
    """Tests for _build_quantity_element function."""

    def test_builds_from_template_with_overrides(self):
        """Test builds quantity element from template with overrides."""
        template = ET.Element("Quantity")
        ET.SubElement(template, "ShippedQty").text = "1000"
        ET.SubElement(template, "ReceivedQty").text = "0"

        values = {"Quantity": {"ShippedQty": "500"}}
        result = _build_quantity_element(template, values)

        assert result.find("ShippedQty").text == "500"
        assert result.find("ReceivedQty").text == "0"

    def test_adds_default_fields_when_missing(self):
        """Test adds default fields when missing from template."""
        template = ET.Element("Quantity")
        values = {}

        result = _build_quantity_element(template, values)

        assert result.find("ShippedQty") is not None
        assert result.find("ShippedQty").text == "2000"
        assert result.find("ReceivedQty") is not None
        assert result.find("ReceivedQty").text == "0"
        assert result.find("QtyUOM") is not None
        assert result.find("QtyUOM").text == "Unit"

    def test_handles_overrides_with_extra_fields(self):
        """Test handles overrides including extra fields."""
        template = ET.Element("Quantity")
        ET.SubElement(template, "ShippedQty").text = "1000"

        values = {"Quantity": {"ShippedQty": "500"}}

        result = _build_quantity_element(template, values)

        # ShippedQty should be updated from override
        assert result.find("ShippedQty").text == "500"

        # Default fields should still be added
        assert result.find("ReceivedQty") is not None
        assert result.find("QtyUOM") is not None


class TestCurrentTimestamp:
    """Tests for _current_timestamp function."""

    def test_returns_datetime_with_timezone(self):
        """Test returns datetime with timezone."""
        result = _current_timestamp()
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    @patch('core.post_message_payload.datetime')
    def test_fallback_when_timezone_fails(self, mock_datetime):
        """Test falls back to datetime.now() on error."""
        mock_datetime.now.side_effect = [Exception("Timezone error"), datetime(2023, 1, 1)]

        result = _current_timestamp()
        assert isinstance(result, datetime)


class TestCustomizeASNPayload:
    """Tests for customize_asn_payload function."""

    def test_customizes_asn_with_new_id(self):
        """Test customizes ASN with new ASNID."""
        xml = """<?xml version="1.0"?>
        <root>
            <ASN>
                <ASNID>OLD123</ASNID>
                <BillOfLadingNumber>BOL123</BillOfLadingNumber>
            </ASN>
        </root>"""

        result_xml, metadata = customize_asn_payload(xml, None)

        # Parse result
        root = ET.fromstring(result_xml)
        asn = root.find(".//ASN")
        new_asn_id = asn.findtext("ASNID")

        # Should have new ASNID (timestamp-based)
        assert new_asn_id != "OLD123"
        assert len(new_asn_id) == 12  # YYMMDDHHMMSS format

        # Metadata should contain new asn_id
        assert "asn_id" in metadata
        assert metadata["asn_id"] == new_asn_id
        assert metadata["created_from"] == "OLD123"

    def test_returns_original_on_parse_error(self):
        """Test returns original payload on XML parse error."""
        invalid_xml = "not valid xml"
        result_xml, metadata = customize_asn_payload(invalid_xml, None)

        assert result_xml == invalid_xml
        assert metadata == {}

    def test_returns_original_when_no_asn_element(self):
        """Test returns original when no ASN element."""
        xml = """<?xml version="1.0"?><root></root>"""
        result_xml, metadata = customize_asn_payload(xml, None)

        assert result_xml == xml
        assert metadata == {}

    def test_customizes_with_items(self):
        """Test customizes ASN with custom items."""
        xml = """<?xml version="1.0"?>
        <root>
            <ASN>
                <ASNID>OLD123</ASNID>
                <ASNDetail>
                    <SequenceNumber>1</SequenceNumber>
                    <ItemName>TEMPLATE_ITEM</ItemName>
                    <Quantity>
                        <ShippedQty>1000</ShippedQty>
                    </Quantity>
                </ASNDetail>
            </ASN>
        </root>"""

        items = [
            {"ItemName": "ITEM1", "Quantity": {"ShippedQty": "100"}},
            {"ItemName": "ITEM2", "Quantity": {"ShippedQty": "200"}},
        ]

        result_xml, metadata = customize_asn_payload(xml, items)

        # Parse result
        root = ET.fromstring(result_xml)
        asn = root.find(".//ASN")
        details = asn.findall("ASNDetail")

        # Should have 2 details (matching items)
        assert len(details) == 2

        # Check first item
        assert details[0].findtext("ItemName") == "ITEM1"
        assert details[0].find("Quantity").findtext("ShippedQty") == "100"

        # Check second item
        assert details[1].findtext("ItemName") == "ITEM2"
        assert details[1].find("Quantity").findtext("ShippedQty") == "200"

        # Metadata should contain receive_items
        assert "receive_items" in metadata
        assert len(metadata["receive_items"]) == 2
        assert metadata["receive_items"][0] == {"item": "ITEM1", "quantity": 100}
        assert metadata["receive_items"][1] == {"item": "ITEM2", "quantity": 200}

    def test_removes_multiple_asnid_elements(self):
        """Test removes multiple ASNID elements before adding new one."""
        xml = """<?xml version="1.0"?>
        <root>
            <ASN>
                <ASNID>OLD1</ASNID>
                <ASNID>OLD2</ASNID>
                <BillOfLadingNumber>BOL</BillOfLadingNumber>
            </ASN>
        </root>"""

        result_xml, metadata = customize_asn_payload(xml, None)

        # Parse result
        root = ET.fromstring(result_xml)
        asn = root.find(".//ASN")
        asnid_elements = asn.findall("ASNID")

        # Should have exactly one ASNID
        assert len(asnid_elements) == 1


class TestBuildPostMessagePayload:
    """Tests for build_post_message_payload function."""

    def test_returns_direct_message_when_source_not_db(self):
        """Test returns direct message when source is not 'db'."""
        post_cfg = {"source": "file", "message": "test message"}

        result, metadata = build_post_message_payload(post_cfg, "ASN", "FC01")

        assert result == "test message"
        assert metadata == {}

    def test_returns_none_when_invalid_message_type(self):
        """Test returns None when message type is invalid."""
        post_cfg = {"source": "db"}

        result, metadata = build_post_message_payload(post_cfg, "invalid", "FC01")

        assert result is None
        assert metadata == {}

    def test_returns_none_when_no_facility_or_object_id(self):
        """Test returns None when no facility or object_id."""
        post_cfg = {"source": "db"}

        result, metadata = build_post_message_payload(post_cfg, "ASN", None)

        assert result is None
        assert metadata == {}

    @patch('core.post_message_payload.DB')
    @patch('random.choice')
    def test_fetches_from_db_with_facility(self, mock_random_choice, mock_db_class):
        """Test fetches payload from database with facility."""
        # Setup mock DB
        mock_db = MagicMock()
        mock_db_class.return_value.__enter__.return_value = mock_db

        # Mock random.choice to always return 0 (first element)
        mock_random_choice.return_value = 0

        # Mock the query results - return 20 rows as expected
        rows = [[f"ASN{i}", "2023-01-01"] for i in range(20)]
        mock_db.fetchall.return_value = (
            rows,
            ["OBJECT_ID", "CREATED_DTTM"]
        )

        # Mock the XML fetch
        mock_payload = MagicMock()
        mock_payload.read.return_value = """<?xml version="1.0"?>
        <root>
            <ASN>
                <ASNID>ASN0</ASNID>
            </ASN>
        </root>"""

        mock_db.fetchone.return_value = {"COMPLETE_XML": mock_payload}

        post_cfg = {"source": "db", "lookback_days": 7}

        result, metadata = build_post_message_payload(post_cfg, "ASN", "FC01")

        # Should have called the database
        assert mock_db.runSQL.called
        assert result is not None
        assert "ASN" in result

    @patch('core.post_message_payload.DB')
    def test_uses_explicit_object_id(self, mock_db_class):
        """Test uses explicit object_id when provided."""
        # Setup mock DB
        mock_db = MagicMock()
        mock_db_class.return_value.__enter__.return_value = mock_db

        # Mock the XML fetch
        mock_payload = MagicMock()
        mock_payload.read.return_value = """<?xml version="1.0"?>
        <root>
            <ASN>
                <ASNID>EXPLICIT123</ASNID>
            </ASN>
        </root>"""

        mock_db.fetchone.return_value = {"COMPLETE_XML": mock_payload}

        post_cfg = {"source": "db", "object_id": "EXPLICIT123"}

        result, metadata = build_post_message_payload(post_cfg, "ASN", "FC01")

        # Should not have called fetchall (no object_id query)
        assert not mock_db.fetchall.called
        # Should have fetched the XML
        assert result is not None

    @patch('core.post_message_payload.DB')
    def test_returns_none_when_no_payload_found(self, mock_db_class):
        """Test returns None when no payload found in DB."""
        # Setup mock DB
        mock_db = MagicMock()
        mock_db_class.return_value.__enter__.return_value = mock_db

        # Mock no results
        mock_db.fetchone.return_value = None

        post_cfg = {"source": "db", "object_id": "NOTFOUND"}

        result, metadata = build_post_message_payload(post_cfg, "ASN", "FC01")

        assert result is None

    @patch('core.post_message_payload.DB')
    def test_customizes_asn_with_items(self, mock_db_class):
        """Test customizes ASN payload with items."""
        # Setup mock DB
        mock_db = MagicMock()
        mock_db_class.return_value.__enter__.return_value = mock_db

        # Mock the XML fetch
        mock_payload = MagicMock()
        mock_payload.read.return_value = """<?xml version="1.0"?>
        <root>
            <ASN>
                <ASNID>ASN123</ASNID>
            </ASN>
        </root>"""

        mock_db.fetchone.return_value = {"COMPLETE_XML": mock_payload}

        post_cfg = {
            "source": "db",
            "object_id": "ASN123",
            "asn_items": [{"ItemName": "ITEM1", "Quantity": 100}]
        }

        result, metadata = build_post_message_payload(post_cfg, "ASN", "FC01")

        # Should have metadata with asn_id
        assert "asn_id" in metadata
        # Should have customized the payload
        assert result is not None
