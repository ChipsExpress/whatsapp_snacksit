import json
import os
from pathlib import Path
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv


load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True, encoding="utf-8-sig")


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_KEY")
    or ""
)


class ConversationStoreError(RuntimeError):
    pass


def is_configured():
    return bool(SUPABASE_URL and SUPABASE_KEY)


def save_inbound_message(payload):
    phone_number = _clean_whatsapp_address(payload.get("From"))
    body = str(payload.get("Body") or "").strip()
    message_sid = str(payload.get("MessageSid") or "").strip()
    profile_name = str(payload.get("ProfileName") or "").strip()

    if not phone_number:
        raise ConversationStoreError("Twilio webhook did not include From.")

    conversation = _upsert_conversation(
        phone_number=phone_number,
        customer_name=profile_name,
        last_message=body,
        unread_increment=1,
    )
    message = _insert_message(
        conversation_id=conversation["id"],
        phone_number=phone_number,
        direction="inbound",
        body=body,
        message_sid=message_sid,
        status="received",
        raw_payload=payload,
    )
    return {"conversation": conversation, "message": message}


def save_outbound_message(phone_number, body, message_sid="", status="queued"):
    phone_number = _clean_whatsapp_address(phone_number)
    if not phone_number:
        raise ConversationStoreError("Outbound message needs a phone number.")

    conversation = _upsert_conversation(
        phone_number=phone_number,
        customer_name="",
        last_message=body,
        unread_increment=0,
    )
    message = _insert_message(
        conversation_id=conversation["id"],
        phone_number=phone_number,
        direction="outbound",
        body=body,
        message_sid=message_sid,
        status=status,
        raw_payload={},
    )
    return {"conversation": conversation, "message": message}


def update_message_status(payload):
    message_sid = str(payload.get("MessageSid") or payload.get("SmsSid") or "").strip()
    status = str(payload.get("MessageStatus") or payload.get("SmsStatus") or "").strip()
    if not message_sid or not status:
        return None

    updated_rows = _supabase_request(
        "PATCH",
        "messages",
        query={"message_sid": f"eq.{message_sid}"},
        body={"status": status, "raw_payload": payload},
        prefer="return=representation",
    )
    return updated_rows[0] if updated_rows else None


def fetch_conversations(limit=50):
    if not is_configured():
        return []

    return _supabase_request(
        "GET",
        "conversations",
        query={
            "select": "*",
            "order": "last_message_time.desc.nullslast",
            "limit": str(limit),
        },
    )


def fetch_messages(conversation_id, limit=100):
    if not is_configured() or not conversation_id:
        return []

    return _supabase_request(
        "GET",
        "messages",
        query={
            "select": "*",
            "conversation_id": f"eq.{conversation_id}",
            "order": "created_at.asc",
            "limit": str(limit),
        },
    )


def mark_conversation_read(conversation_id):
    if not is_configured() or not conversation_id:
        return None

    rows = _supabase_request(
        "PATCH",
        "conversations",
        query={"id": f"eq.{conversation_id}"},
        body={"unread_count": 0},
        prefer="return=representation",
    )
    return rows[0] if rows else None


def _upsert_conversation(phone_number, customer_name, last_message, unread_increment):
    existing = _find_conversation(phone_number)
    timestamp = _now_iso()

    if existing:
        unread_count = int(existing.get("unread_count") or 0) + unread_increment
        rows = _supabase_request(
            "PATCH",
            "conversations",
            query={"id": f"eq.{existing['id']}"},
            body={
                "customer_name": customer_name or existing.get("customer_name") or "",
                "last_message": last_message,
                "last_message_time": timestamp,
                "unread_count": unread_count,
                "status": existing.get("status") or "open",
            },
            prefer="return=representation",
        )
        return rows[0]

    rows = _supabase_request(
        "POST",
        "conversations",
        body={
            "phone_number": phone_number,
            "customer_name": customer_name or "",
            "last_message": last_message,
            "last_message_time": timestamp,
            "unread_count": unread_increment,
            "status": "open",
        },
        prefer="return=representation",
    )
    return rows[0]


def _find_conversation(phone_number):
    rows = _supabase_request(
        "GET",
        "conversations",
        query={
            "select": "*",
            "phone_number": f"eq.{phone_number}",
            "limit": "1",
        },
    )
    return rows[0] if rows else None


def _insert_message(conversation_id, phone_number, direction, body, message_sid, status, raw_payload):
    rows = _supabase_request(
        "POST",
        "messages",
        body={
            "conversation_id": conversation_id,
            "phone_number": phone_number,
            "direction": direction,
            "body": body,
            "message_sid": message_sid,
            "status": status,
            "raw_payload": raw_payload,
        },
        prefer="return=representation",
    )
    return rows[0]


def _supabase_request(method, table, query=None, body=None, prefer=""):
    if not is_configured():
        raise ConversationStoreError(
            "Missing Supabase config. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )

    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if query:
        url = f"{url}?{urlencode(query)}"

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer

    request = Request(url, data=data, method=method, headers=headers)

    try:
        with urlopen(request, timeout=20) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise ConversationStoreError(
            f"Supabase request failed ({exc.code}): {error_body}"
        ) from exc
    except URLError as exc:
        raise ConversationStoreError(f"Unable to reach Supabase: {exc.reason}") from exc

    if not response_body:
        return []

    return json.loads(response_body)


def _clean_whatsapp_address(value):
    phone_number = str(value or "").strip()
    if phone_number.startswith("whatsapp:"):
        phone_number = phone_number.replace("whatsapp:", "", 1)
    return phone_number


def _now_iso():
    return datetime.now(timezone.utc).isoformat()



