"""Additional coverage for post_message_payload helpers."""
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import core.post_message_payload as pmp


class StubDB:
    def __init__(self, rows=None, columns=None, fetchone_result=None):
        self.rows = rows or []
        self.columns = columns or []
        self.fetchone_result = fetchone_result
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def runSQL(self, query, whse_specific=True):
        self.queries.append(query)
        return self

    def fetchall(self):
        return self.rows, self.columns

    def fetchone(self):
        return self.fetchone_result


def test_build_post_message_payload_handles_missing_object(monkeypatch):
    stub_db = StubDB(rows=[], columns=[])
    monkeypatch.setattr(pmp, "DB", lambda env: stub_db)

    payload, meta = pmp.build_post_message_payload(
        {"type": "asn", "lookback_days": 1}, "asn", facility="FAC1"
    )
    assert payload is None
    assert meta == {}


def test_fetch_recent_object_id_distribution_order(monkeypatch):
    stub_db = StubDB(rows=[("DO-1",)], columns=["OBJECT_ID"])
    monkeypatch.setattr("random.choice", lambda seq: 0)
    result = pmp._fetch_recent_object_id(
        stub_db, "DistributionOrder", "FAC", lookback_days=1, record_index=0
    )
    assert result == "DO-1"
    assert "ORDERS" in stub_db.queries[0]


def test_fetch_message_xml_uses_clob_helpers(monkeypatch):
    class Payload:
        def getvalue(self):
            return "  <xml>payload</xml>  "

    stub_db = StubDB(fetchone_result={"COMPLETE_XML": Payload()})
    payload = pmp._fetch_message_xml(stub_db, "ASN", "OBJ1")
    assert payload == "<xml>payload</xml>"


def test_fetch_message_xml_falls_back_on_exception(monkeypatch):
    class BadPayload:
        def getSubString(self, *_args, **_kwargs):
            raise RuntimeError("boom")

        def length(self):
            return "invalid"

        def __str__(self):
            return "fallback"

    stub_db = StubDB(fetchone_result={"COMPLETE_XML": BadPayload()})
    payload = pmp._fetch_message_xml(stub_db, "ASN", "OBJ1")
    assert payload == "fallback"


def test_build_detail_from_template_handles_purchase_order_fields():
    template = ET.Element("ASNDetail")
    ET.SubElement(template, "SequenceNumber").text = None
    qty = ET.SubElement(template, "Quantity")
    ET.SubElement(qty, "ShippedQty")
    ET.SubElement(qty, "ReceivedQty")
    ET.SubElement(qty, "QtyUOM")
    ET.SubElement(template, "PurchaseOrderLineItemID").text = "1"
    ET.SubElement(template, "PurchaseOrderID").text = "PO1"
    ET.SubElement(template, "Sku").text = "ABC"

    values = {
        "PurchaseOrderLineItemID": "99",
        "Quantity": {"ShippedQty": None, "ExtraField": "X"},
        "NewField": "NEW",
    }

    detail = pmp._build_detail_from_template(
        template_detail=template,
        values=values,
        seq_prefix="SEQ",
        index=0,
        po_override="OVERRIDE",
    )

    tags = [child.tag for child in detail]
    assert "PurchaseOrderLineItemID" in tags
    assert "PurchaseOrderID" in tags
    assert any(child.tag == "Quantity" for child in detail)
    assert any(child.tag == "NewField" for child in detail)

    qty_elem = next(child for child in detail if child.tag == "Quantity")
    extra = [
        child
        for child in qty_elem
        if child.tag.lower() not in {"shippedqty", "receivedqty", "qtyuom"}
    ]
    assert any(child.tag.lower() == "extrafield" for child in extra)


def test_derive_quantity_for_receive_handles_invalid_shipped():
    item = {"Quantity": {"ShippedQty": "not-a-number"}}
    assert pmp._derive_quantity_for_receive(item) == 2000
