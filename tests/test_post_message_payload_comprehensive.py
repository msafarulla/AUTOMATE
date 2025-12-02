"""
Comprehensive tests for core/post_message_payload.py (CRITICAL - was 8% coverage).
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from core.post_message_payload import (
    build_post_message_payload,
    customize_asn_payload,
    _normalize_msg_type,
    _fetch_recent_object_id,
    _fetch_message_xml,
    _current_timestamp,
    _extract_asn_id,
    _value_case_insensitive,
    _values_have_quantity,
    _set_child_text,
    _extract_quantity_overrides,
    _default_quantity_value,
    _build_receive_items,
    _derive_quantity_for_receive,
    _build_quantity_element,
    _build_detail_from_template,
    _resolve_tag_case,
)


class TestNormalizeMsgType:
    """Test message type normalization."""

    def test_normalize_asn(self):
        """Test normalizing ASN type."""
        assert _normalize_msg_type("asn") == "ASN"
        assert _normalize_msg_type("ASN") == "ASN"
        assert _normalize_msg_type("  asn  ") == "ASN"

    def test_normalize_distribution_order(self):
        """Test normalizing distribution order types."""
        assert _normalize_msg_type("distributionorder") == "DistributionOrder"
        assert _normalize_msg_type("do") == "DistributionOrder"
        assert _normalize_msg_type("order") == "DistributionOrder"
        assert _normalize_msg_type("DO") == "DistributionOrder"

    def test_normalize_none(self):
        """Test normalizing None."""
        assert _normalize_msg_type(None) is None

    def test_normalize_empty_string(self):
        """Test normalizing empty string."""
        assert _normalize_msg_type("") is None
        assert _normalize_msg_type("   ") is None

    def test_normalize_unknown_type(self):
        """Test normalizing unknown type."""
        assert _normalize_msg_type("unknown") is None
        assert _normalize_msg_type("invoice") is None


class TestCurrentTimestamp:
    """Test current timestamp function."""

    def test_current_timestamp_returns_datetime(self):
        """Test that current timestamp returns datetime."""
        result = _current_timestamp()
        assert isinstance(result, datetime)

    def test_current_timestamp_recent(self):
        """Test timestamp is recent."""
        ts = _current_timestamp()
        now = datetime.now()
        diff = abs((ts - now).total_seconds())
        assert diff < 2  # Should be within 2 seconds

    @patch('core.post_message_payload.datetime')
    def test_current_timestamp_fallback(self, mock_datetime):
        """Test timestamp fallback when UTC fails."""
        mock_datetime.now.side_effect = [Exception("UTC error"), datetime(2024, 1, 1, 12, 0, 0)]
        result = _current_timestamp()
        assert result == datetime(2024, 1, 1, 12, 0, 0)


class TestExtractASNId:
    """Test ASN ID extraction from XML."""

    def test_extract_asn_id_success(self):
        """Test extracting ASN ID from valid XML."""
        xml_payload = '''<?xml version="1.0"?>
        <root>
            <ASN>
                <ASNID>ASN123456</ASNID>
            </ASN>
        </root>'''
        assert _extract_asn_id(xml_payload) == "ASN123456"

    def test_extract_asn_id_no_asn_element(self):
        """Test extracting from XML without ASN element."""
        xml_payload = '''<?xml version="1.0"?>
        <root><other>data</other></root>'''
        assert _extract_asn_id(xml_payload) is None

    def test_extract_asn_id_no_asnid(self):
        """Test extracting when ASNID is missing."""
        xml_payload = '''<?xml version="1.0"?>
        <root><ASN><other>data</other></ASN></root>'''
        assert _extract_asn_id(xml_payload) is None

    def test_extract_asn_id_invalid_xml(self):
        """Test extracting from invalid XML."""
        assert _extract_asn_id("not xml") is None
        assert _extract_asn_id("") is None


class TestValueCaseInsensitive:
    """Test case-insensitive value lookup."""

    def test_exact_match(self):
        """Test exact key match."""
        values = {"Name": "John", "Age": 30}
        assert _value_case_insensitive(values, "Name") == "John"

    def test_different_case(self):
        """Test case-insensitive match."""
        values = {"ItemName": "ITEM001", "Quantity": 10}
        assert _value_case_insensitive(values, "itemname") == "ITEM001"
        assert _value_case_insensitive(values, "ITEMNAME") == "ITEM001"

    def test_no_match(self):
        """Test when key doesn't exist."""
        values = {"Name": "John"}
        assert _value_case_insensitive(values, "Age") is None

    def test_empty_dict(self):
        """Test with empty dictionary."""
        assert _value_case_insensitive({}, "key") is None


class TestValuesHaveQuantity:
    """Test quantity detection in values."""

    def test_has_quantity_lowercase(self):
        """Test detecting lowercase quantity."""
        assert _values_have_quantity({"quantity": 10}) is True

    def test_has_quantity_uppercase(self):
        """Test detecting uppercase quantity."""
        assert _values_have_quantity({"Quantity": 10}) is True

    def test_has_quantity_mixed_case(self):
        """Test detecting mixed case quantity."""
        assert _values_have_quantity({"QuAnTiTy": 10}) is True

    def test_no_quantity(self):
        """Test when quantity is absent."""
        assert _values_have_quantity({"item": "ABC"}) is False

    def test_empty_dict(self):
        """Test with empty dictionary."""
        assert _values_have_quantity({}) is False


class TestExtractQuantityOverrides:
    """Test quantity override extraction."""

    def test_extract_quantity_dict_lowercase(self):
        """Test extracting quantity from lowercase key."""
        values = {"quantity": {"ShippedQty": 100, "ReceivedQty": 0}}
        result = _extract_quantity_overrides(values)
        assert result == {"shippedqty": 100, "receivedqty": 0}

    def test_extract_quantity_dict_uppercase(self):
        """Test extracting quantity from uppercase key."""
        values = {"Quantity": {"ShippedQty": 50}}
        result = _extract_quantity_overrides(values)
        assert result == {"shippedqty": 50}

    def test_extract_quantity_not_dict(self):
        """Test when quantity is not a dict."""
        values = {"quantity": 10}
        result = _extract_quantity_overrides(values)
        assert result == {}

    def test_extract_no_quantity(self):
        """Test when no quantity exists."""
        result = _extract_quantity_overrides({"item": "ABC"})
        assert result == {}


class TestDefaultQuantityValue:
    """Test default quantity value generation."""

    def test_default_shipped_qty(self):
        """Test default for shipped quantity."""
        assert _default_quantity_value("shippedqty") == "2000"

    def test_default_received_qty(self):
        """Test default for received quantity."""
        assert _default_quantity_value("receivedqty") == "0"

    def test_default_qty_uom(self):
        """Test default for quantity UOM."""
        assert _default_quantity_value("qtyuom") == "Unit"

    def test_default_unknown(self):
        """Test default for unknown tag."""
        assert _default_quantity_value("other") == ""


class TestDeriveQuantityForReceive:
    """Test quantity derivation for receive."""

    def test_derive_from_quantity_mapping(self):
        """Test deriving from Quantity mapping."""
        item = {"Quantity": {"ShippedQty": 150}}
        assert _derive_quantity_for_receive(item) == 150

    def test_derive_from_quantity_mapping_lowercase(self):
        """Test deriving from quantity mapping (lowercase)."""
        item = {"quantity": {"shippedqty": 75}}
        assert _derive_quantity_for_receive(item) == 75

    def test_derive_from_direct_int(self):
        """Test deriving from direct integer."""
        item = {"quantity": 50}
        assert _derive_quantity_for_receive(item) == 50

    def test_derive_from_direct_string(self):
        """Test deriving from string quantity."""
        item = {"Quantity": "25"}
        assert _derive_quantity_for_receive(item) == 25

    def test_derive_invalid_string(self):
        """Test deriving from invalid string."""
        item = {"quantity": "abc"}
        assert _derive_quantity_for_receive(item) == 2000

    def test_derive_default(self):
        """Test default quantity."""
        item = {"item": "ABC"}
        assert _derive_quantity_for_receive(item) == 2000


class TestBuildReceiveItems:
    """Test building receive items list."""

    def test_build_single_item(self):
        """Test building single receive item."""
        items = [{"ItemName": "ITEM001", "quantity": 10}]
        result = _build_receive_items(items)
        assert result == [{"item": "ITEM001", "quantity": 10}]

    def test_build_multiple_items(self):
        """Test building multiple receive items."""
        items = [
            {"ItemName": "ITEM001", "Quantity": 10},
            {"item": "ITEM002", "quantity": 20}
        ]
        result = _build_receive_items(items)
        assert len(result) == 2
        assert result[0]["item"] == "ITEM001"
        assert result[1]["item"] == "ITEM002"

    def test_build_skip_empty(self):
        """Test skipping empty items."""
        items = [{"ItemName": "ITEM001", "quantity": 10}, None, {}]
        result = _build_receive_items(items)
        assert len(result) == 1

    def test_build_skip_no_item_name(self):
        """Test skipping items without name."""
        items = [{"quantity": 10}]
        result = _build_receive_items(items)
        assert result == []

    def test_build_empty_list(self):
        """Test with empty list."""
        assert _build_receive_items([]) == []


class TestSetChildText:
    """Test setting child text in XML element."""

    def test_set_new_child(self):
        """Test setting text on new child."""
        parent = ET.Element("parent")
        result = _set_child_text(parent, "child", "value")
        assert result is not None
        assert parent.find("child").text == "value"

    def test_set_existing_child(self):
        """Test updating existing child."""
        parent = ET.Element("parent")
        ET.SubElement(parent, "child").text = "old"
        _set_child_text(parent, "child", "new")
        assert parent.find("child").text == "new"

    def test_set_none_value(self):
        """Test setting None value."""
        parent = ET.Element("parent")
        result = _set_child_text(parent, "child", None)
        assert result is None
        assert parent.find("child") is None

    def test_set_with_insert_index(self):
        """Test setting child at specific index."""
        parent = ET.Element("parent")
        ET.SubElement(parent, "first")
        ET.SubElement(parent, "second")
        _set_child_text(parent, "new", "value", insert_index=0)
        assert list(parent)[0].tag == "new"


class TestResolveTagCase:
    """Test case-insensitive tag resolution."""

    def test_resolve_exact_match(self):
        """Test resolving with exact match."""
        parent = ET.Element("parent")
        child = ET.SubElement(parent, "Child")
        result = _resolve_tag_case(parent, "Child")
        assert result == child

    def test_resolve_different_case(self):
        """Test resolving with different case."""
        parent = ET.Element("parent")
        child = ET.SubElement(parent, "ItemName")
        result = _resolve_tag_case(parent, "itemname")
        assert result == child

    def test_resolve_not_found(self):
        """Test when tag is not found."""
        parent = ET.Element("parent")
        ET.SubElement(parent, "other")
        result = _resolve_tag_case(parent, "missing")
        assert result is None


class TestBuildQuantityElement:
    """Test building quantity XML element."""

    def test_build_quantity_basic(self):
        """Test building basic quantity element."""
        template = ET.Element("Quantity")
        ET.SubElement(template, "ShippedQty").text = "100"
        values = {}
        result = _build_quantity_element(template, values)
        assert result.tag == "Quantity"
        assert result.find("ShippedQty").text == "100"

    def test_build_quantity_with_overrides(self):
        """Test building quantity with overrides."""
        template = ET.Element("Quantity")
        values = {"Quantity": {"ShippedQty": 200}}
        result = _build_quantity_element(template, values)
        assert result.find("ShippedQty").text == "200"

    def test_build_quantity_adds_defaults(self):
        """Test that defaults are added."""
        template = ET.Element("Quantity")
        values = {}
        result = _build_quantity_element(template, values)
        # Should have defaults
        assert result.find("ShippedQty") is not None
        assert result.find("ReceivedQty") is not None
        assert result.find("QtyUOM") is not None


class TestBuildPostMessagePayload:
    """Test building post message payload (main function)."""

    def test_build_non_db_source(self):
        """Test with non-database source."""
        post_cfg = {"source": "file", "message": "test message"}
        result_msg, metadata = build_post_message_payload(post_cfg, "ASN", "FAC1")
        assert result_msg == "test message"
        assert metadata == {}

    def test_build_missing_message_type(self):
        """Test with missing message type."""
        post_cfg = {"source": "db"}
        result_msg, metadata = build_post_message_payload(post_cfg, "", "FAC1")
        assert result_msg is None
        assert metadata == {}

    def test_build_no_facility_or_object_id(self):
        """Test with no facility or object ID."""
        post_cfg = {"source": "db"}
        result_msg, metadata = build_post_message_payload(post_cfg, "ASN", None)
        assert result_msg is None
        assert metadata == {}

    @patch('core.post_message_payload.DB')
    def test_build_with_explicit_object_id(self, mock_db_class):
        """Test with explicit object ID."""
        mock_db = MagicMock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db_class.return_value.__exit__.return_value = None

        # Mock fetch message XML
        mock_db.runSQL = MagicMock()
        mock_db.fetchone.return_value = {"COMPLETE_XML": "<root><ASN><ASNID>ASN123</ASNID></ASN></root>"}

        post_cfg = {
            "source": "db",
            "object_id": "OBJ123",
            "db_env": "dev"
        }

        result_msg, metadata = build_post_message_payload(post_cfg, "ASN", "FAC1")

        # Should have called DB with the query
        assert mock_db.runSQL.called


class TestCustomizeASNPayload:
    """Test ASN payload customization."""

    def test_customize_asn_basic(self):
        """Test basic ASN customization."""
        payload = '''<?xml version="1.0"?>
<root>
    <ASN>
        <ASNID>OLD123</ASNID>
        <BillOfLadingNumber>BOL123</BillOfLadingNumber>
    </ASN>
</root>'''

        result_xml, metadata = customize_asn_payload(payload, None)

        # Should have new ASN ID
        root = ET.fromstring(result_xml)
        asn = root.find(".//ASN")
        assert asn.findtext("ASNID") != "OLD123"
        assert "asn_id" in metadata

    def test_customize_asn_invalid_xml(self):
        """Test customizing invalid XML."""
        result_xml, metadata = customize_asn_payload("not xml", None)
        assert result_xml == "not xml"
        assert metadata == {}

    def test_customize_asn_no_asn_element(self):
        """Test customizing XML without ASN element."""
        payload = '''<?xml version="1.0"?><root><other>data</other></root>'''
        result_xml, metadata = customize_asn_payload(payload, None)
        assert result_xml == payload
        assert metadata == {}

    def test_customize_asn_with_items(self):
        """Test customizing with item list."""
        payload = '''<?xml version="1.0"?>
<root>
    <ASN>
        <ASNID>OLD123</ASNID>
        <ASNDetail>
            <ItemName>TEMPLATE</ItemName>
            <Quantity><ShippedQty>1000</ShippedQty></Quantity>
        </ASNDetail>
    </ASN>
</root>'''

        items = [
            {"ItemName": "ITEM001", "Quantity": 10},
            {"ItemName": "ITEM002", "Quantity": 20}
        ]

        result_xml, metadata = customize_asn_payload(payload, items)

        # Should have replaced details
        root = ET.fromstring(result_xml)
        asn = root.find(".//ASN")
        details = asn.findall("ASNDetail")
        assert len(details) == 2
        assert "receive_items" in metadata
        assert len(metadata["receive_items"]) == 2


@pytest.mark.integration
class TestPostMessagePayloadIntegration:
    """Integration tests requiring database."""

    def test_full_payload_build_with_db(self):
        """Test full payload building with database."""
        # Placeholder for integration test
        pass
