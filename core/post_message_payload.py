from __future__ import annotations

from datetime import datetime
import xml.etree.ElementTree as ET
from typing import Any, Iterable, Mapping, Optional, Sequence

from DB import DB
from core.logger import app_log


def build_post_message_payload(
    post_cfg: dict,
    message_type: str,
    facility: Optional[str],
    db_env: Optional[str] = None
) -> tuple[Optional[str], dict[str, Any]]:

    source = (post_cfg.get("source") or "db").lower()
    if source != "db":
        return post_cfg.get("message"), {}

    normalized_type = _normalize_msg_type(message_type)
    if not normalized_type:
        app_log("⚠️ Post message config missing/invalid message type.")
        return None, {}

    object_id = post_cfg.get("object_id")
    lookback_days = int(post_cfg.get("lookback_days", 14))
    record_index = max(0, int(post_cfg.get("record_index", 0)))
    resolved_db_env = db_env or post_cfg.get("db_env")

    if not object_id and not facility:
        app_log("⚠️ Post message payload requires facility or explicit object_id.")
        return None, {}

    db_target = resolved_db_env or "qa"

    with DB(db_target) as db:
        if not object_id:
            object_id = _fetch_recent_object_id(
                db,
                normalized_type,
                facility,
                lookback_days,
                record_index,
            )
        if not object_id:
            app_log("⚠️ No matching object id found for post message payload.")
            return None, {}

        payload = _fetch_message_xml(db, normalized_type, object_id)
        metadata: dict[str, Any] = {}
        if not payload:
            app_log(f"⚠️ No XML payload located for {message_type} object {object_id}.")
            return None, metadata

        if normalized_type == "ASN":
            metadata["asn_id"] = _extract_asn_id(payload)
            items = post_cfg.get("asn_items")
            if isinstance(items, Sequence) and not isinstance(items, (str, bytes)) and items:
                payload, custom_meta = customize_asn_payload(payload, items)
                metadata.update(custom_meta)

        return payload, metadata


def _normalize_msg_type(msg_type: Optional[str]) -> Optional[str]:
    if not msg_type:
        return None
    normalized = msg_type.strip().lower()
    if normalized in {"asn"}:
        return "ASN"
    if normalized in {"distributionorder", "do", "order"}:
        return "DistributionOrder"
    return None


def _fetch_recent_object_id(
    db: DB,
    message_type: str,
    facility: str,
    lookback_days: int,
    record_index: int,
) -> Optional[str]:

    if message_type == "ASN":
        query = f"""
            select TC_ASN_ID as OBJECT_ID, CREATED_DTTM
            from ASN
            where DESTINATION_FACILITY_ALIAS_ID = '{facility}'
              and CREATED_DTTM >= sysdate - interval '{lookback_days}' day
              and TC_ASN_ID in (select OBJECT_ID from TRAN_LOG where MSG_TYPE  = 'ASN')
            order by CREATED_DTTM desc fetch first 2 rows only
        """
    else:
        query = f"""
            select TC_ORDER_ID as OBJECT_ID, CREATED_DTTM
            from ORDERS
            where O_FACILITY_ALIAS_ID = '{facility}'
              and CREATED_DTTM >= sysdate - interval '{lookback_days}' day
            order by CREATED_DTTM desc fetch first 2 rows only
        """

    db.runSQL(query)
    rows, columns = db.fetchall()
    if not rows:
        return None

    object_idx = min(record_index, len(rows) - 1)
    col_index = columns.index("OBJECT_ID")
    return rows[object_idx][col_index]


def _fetch_message_xml(db: DB, message_type: str, object_id: str) -> Optional[str]:
    xml_query = f"""
        select
            replace(
                replace(
                    xmlserialize(
                        content xmlagg(
                            xmlcdata(
                                coalesce(MSG_LINE_TEXT, '')
                            )
                            order by MSG_LINE_NUMBER
                        ) as clob
                    ),
                    '<![CDATA[', ''
                ),
                ']]>', ''
            ) as COMPLETE_XML
        from TRAN_LOG_MESSAGE TLM
        where TLM.TRAN_LOG_ID in (
            select TL.TRAN_LOG_ID
            from TRAN_LOG TL
            where TL.OBJECT_ID = '{object_id}'
              and TL.DIRECTION = 'I'
              and TL.MSG_TYPE = '{message_type}'
        )
    """

    db.runSQL(xml_query, whse_specific=False)
    row = db.fetchone()
    if not row:
        return None

    payload = row['COMPLETE_XML']
    if payload is None:
        return None

    payload_text: Optional[str] = None
    try:
        if hasattr(payload, "read"):
            payload_text = payload.read()
        elif hasattr(payload, "getvalue"):
            payload_text = payload.getvalue()
        elif hasattr(payload, "stringValue"):
            payload_text = payload.stringValue()
        elif hasattr(payload, "string"):
            payload_text = payload.string
        elif hasattr(payload, "getSubString") and hasattr(payload, "length"):
            try:
                length = int(payload.length())
            except Exception:
                length = payload.length()
            payload_text = payload.getSubString(1, length)
    except Exception as exc:
        app_log(f"⚠️ Failed to read CLOB payload via native handles: {exc}")

    if payload_text is None:
        payload_text = str(payload)

    payload_text = payload_text.strip()
    return payload_text or None


def customize_asn_payload(payload: str, items: Sequence[Mapping[str, Any]]) -> tuple[str, dict[str, Any]]:
    """
    Rewrite the ASNDetail section for each supplied item/quantity row.
    Each dictionary should provide tag names such as "ItemName", "PurchaseOrderID",
    and an optional "Quantity" sub-mapping; unspecified quantities default to 2000 units.
    Returns the rewritten XML plus metadata (currently just ``asn_id``).
    """
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        app_log(f"⚠️ Unable to parse ASN payload for customization: {exc}")
        return payload, {}

    asn_elem = root.find(".//ASN")
    if asn_elem is None:
        app_log("⚠️ ASN payload customization skipped: <ASN> element not found.")
        return payload, {}

    template_detail = asn_elem.find("ASNDetail")
    timestamp = datetime.utcnow()
    asn_id = timestamp.strftime("%m%y%m%d%H%M%S")
    seq_prefix = timestamp.strftime("%y%m%d%H%M%S")
    for existing_asn_id in asn_elem.findall("ASNID"):
        asn_elem.remove(existing_asn_id)
    _set_child_text(asn_elem, "ASNID", asn_id, insert_index=0)

    metadata: dict[str, Any] = {"asn_id": asn_id}

    for existing in list(asn_elem.findall("ASNDetail")):
        asn_elem.remove(existing)

    if template_detail is None:
        template_detail = ET.Element("ASNDetail")

    for index, item in enumerate(items):
        detail = _build_detail_from_template(template_detail, item, seq_prefix, index)
        asn_elem.append(detail)

    serialized = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    receive_items = _build_receive_items(items)
    if receive_items:
        metadata["receive_items"] = receive_items
    return serialized, metadata


def _build_detail_from_template(
    template_detail: ET.Element,
    values: Mapping[str, Any],
    seq_prefix: str,
    index: int,
) -> ET.Element:
    detail = ET.Element("ASNDetail")
    tags_emitted: set[str] = set()

    for child in template_detail:
        tag = child.tag
        lower_tag = tag.lower()
        tags_emitted.add(lower_tag)

        if lower_tag == "sequencenumber":
            seq_override = _value_case_insensitive(values, "SequenceNumber")
            sequence_text = (
                str(seq_override) if seq_override is not None else f"{seq_prefix}{index + 1:02d}"
            )
            node = ET.Element("SequenceNumber")
            node.text = sequence_text
        elif lower_tag == "quantity":
            node = _build_quantity_element(child, values)
        elif lower_tag == "purchaseorderlineitemid":
            po_line = _value_case_insensitive(values, "PurchaseOrderLineItemID") or str(index + 1)
            node = ET.Element(tag)
            node.text = po_line
        else:
            override = _value_case_insensitive(values, tag)
            node = ET.Element(tag)
            node.text = str(override) if override is not None else child.text or ""

        detail.append(node)

    for key, raw_value in values.items():
        lower_key = key.lower()
        if lower_key in tags_emitted or lower_key in {"quantity", "sequencenumber"}:
            continue
        extra = ET.Element(key)
        extra.text = str(raw_value)
        detail.append(extra)

    return detail


def _build_quantity_element(template_qty: ET.Element, values: Mapping[str, Any]) -> ET.Element:
    overrides = _extract_quantity_overrides(values)
    quantity = ET.Element("Quantity")

    for child in template_qty:
        tag = child.tag
        lower_tag = tag.lower()
        if lower_tag in overrides:
            text = str(overrides.pop(lower_tag))
        else:
            text = child.text
        if text is None:
            text = _default_quantity_value(lower_tag)
        node = ET.Element(tag)
        node.text = str(text)
        quantity.append(node)

    for default_tag, default_value in (
        ("ShippedQty", "2000"),
        ("ReceivedQty", "0"),
        ("QtyUOM", "Unit"),
    ):
        if quantity.find(default_tag) is None:
            node = ET.Element(default_tag)
            node.text = default_value
            quantity.append(node)

    for tag, value in overrides.items():
        extra = ET.Element(tag)
        extra.text = str(value)
        quantity.append(extra)

    return quantity


def _resolve_tag_case(parent: ET.Element, tag: str) -> Optional[ET.Element]:
    lower_tag = tag.lower()
    for child in parent:
        if child.tag.lower() == lower_tag:
            return child
    return None


def _extract_asn_id(payload: str) -> Optional[str]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return None
    asn_elem = root.find(".//ASN")
    if asn_elem is None:
        return None
    return asn_elem.findtext("ASNID")


def _value_case_insensitive(values: Mapping[str, Any], target: str) -> Any | None:
    lower_target = target.lower()
    for raw_key, raw_value in values.items():
        if raw_key.lower() == lower_target:
            return raw_value
    return None


def _coerce_numeric(value: str) -> str:
    try:
        num = int(value)
        return str(num)
    except (ValueError, TypeError):
        return str(value)


def _set_child_text(parent: ET.Element, tag: str, value: Any | None, *, insert_index: Optional[int] = None) -> Optional[ET.Element]:
    if value is None:
        return

    target_tag = _resolve_tag_case(parent, tag)
    node = target_tag or ET.SubElement(parent, tag)
    node.text = str(value)
    if insert_index is not None and target_tag is None:
        parent.remove(node)
        parent.insert(insert_index, node)
    return node


def _extract_quantity_overrides(values: Mapping[str, Any]) -> dict[str, Any]:
    qty = values.get("Quantity") or values.get("quantity")
    if isinstance(qty, Mapping):
        return {key.lower(): val for key, val in qty.items()}
    return {}


def _default_quantity_value(lower_tag: str) -> str:
    if lower_tag == "shippedqty":
        return "2000"
    if lower_tag == "receivedqty":
        return "0"
    if lower_tag == "qtyuom":
        return "Unit"
    return ""


def _build_receive_items(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    receive_items: list[dict[str, Any]] = []
    for item in items:
        if not item:
            continue
        code = _value_case_insensitive(item, "ItemName") or _value_case_insensitive(item, "item")
        if not code:
            continue
        quantity = _derive_quantity_for_receive(item)
        receive_items.append({"item": code, "quantity": quantity})
    return receive_items


def _derive_quantity_for_receive(item: Mapping[str, Any]) -> int:
    qty_map = item.get("Quantity") or item.get("quantity")
    if isinstance(qty_map, Mapping):
        shipped = qty_map.get("ShippedQty") or qty_map.get("shippedqty")
        if shipped is not None:
            try:
                return int(shipped)
            except ValueError:
                pass
    direct_qty = item.get("quantity") or item.get("Quantity")
    if isinstance(direct_qty, int):
        return direct_qty
    if isinstance(direct_qty, str):
        try:
            return int(direct_qty)
        except ValueError:
            pass
    return 2000
