"""
Utilities to build Post Message payloads from the database using canned queries.
"""
from __future__ import annotations

from typing import Optional

from DB import DB
from core.logger import app_log


def build_post_message_payload(post_cfg: dict, message_type: str, facility: Optional[str]) -> Optional[str]:
    """
    Build a Post Message XML payload based on workflow config.

    Supported config keys:
        - source: "db" (default) or "static"
        - facility: Facility alias to filter recent records
        - lookback_days: How far back to search (default 14)
        - record_index: Zero-based index into recent results (default 0)
        - object_id: Explicit object id to use instead of querying
        - db_env: DB environment/alias for the DB() helper (default "qa")
    """
    source = (post_cfg.get("source") or "db").lower()
    if source != "db":
        return post_cfg.get("message")

    normalized_type = _normalize_msg_type(message_type)
    if not normalized_type:
        app_log("⚠️ Post message config missing/invalid message type.")
        return None

    object_id = post_cfg.get("object_id")
    lookback_days = int(post_cfg.get("lookback_days", 14))
    record_index = max(0, int(post_cfg.get("record_index", 0)))
    db_env = post_cfg.get("db_env", "qa")

    if not object_id and not facility:
        app_log("⚠️ Post message payload requires facility or explicit object_id.")
        return None

    with DB(db_env) as db:
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
            return None

        payload = _fetch_message_xml(db, normalized_type, object_id)
        if not payload:
            app_log(f"⚠️ No XML payload located for {message_type} object {object_id}.")
        return payload


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
    """
    Fetch the Nth most recent object id for the given message type and facility.
    Uses the same SQL pattern provided by the operator for consistency/performance.
    """
    if message_type == "ASN":
        query = f"""
            select TC_ASN_ID as OBJECT_ID, CREATED_DTTM
            from ASN
            where DESTINATION_FACILITY_ALIAS_ID = '{facility}'
              and CREATED_DTTM >= sysdate - interval '{lookback_days}' day
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
    """
    Build the XML payload by stitching TRAN_LOG_MESSAGE rows for the given object.
    """
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

    db.runSQL(xml_query)
    row = db.fetchone()
    if not row:
        return None
    payload = row['COMPLETE_XML']
    if payload is None:
        return None
    try:
        payload_text = payload.read() if hasattr(payload, "read") else str(payload)
    except Exception:
        payload_text = str(payload)
    payload_text = payload_text.strip()
    return payload_text or None
