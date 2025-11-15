from __future__ import annotations

from typing import Optional

from DB import DB
from core.logger import app_log


def build_post_message_payload(
    post_cfg: dict,
    message_type: str,
    facility: Optional[str],
    db_env: Optional[str] = None
) -> Optional[str]:

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
    resolved_db_env = db_env or post_cfg.get("db_env")

    if not object_id and not facility:
        app_log("⚠️ Post message payload requires facility or explicit object_id.")
        return None

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