import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID")

META_API_VERSION = "v21.0"


def send_whatsapp_template(to_number, content_sid, content_variables=None, language_code="en_US"):
    """Send one approved Meta WhatsApp template using WhatsApp Business Cloud API."""
    _validate_meta_config()

    if not to_number:
        raise ValueError("Recipient WhatsApp number is required.")

    template_name = str(content_sid).strip()
    if not template_name:
        raise ValueError("WhatsApp Template Name or ID is required.")

    clean_to = _clean_phone_number(to_number)

    template_payload = {
        "name": template_name,
        "language": {
            "code": language_code
        }
    }

    if content_variables:
        components = []
        body_params = []
        header_params = []

        # Sort keys numerically if possible, otherwise string sort
        sorted_keys = sorted(
            content_variables.keys(),
            key=lambda k: int(k) if str(k).isdigit() else str(k)
        )

        for k in sorted_keys:
            val = str(content_variables[k])
            # Check if variable is a media URL (image)
            if val.startswith("http://") or val.startswith("https://"):
                header_params.append({
                    "type": "image",
                    "image": {"link": val}
                })
            else:
                body_params.append({
                    "type": "text",
                    "text": val
                })

        if header_params:
            components.append({
                "type": "header",
                "parameters": header_params
            })
        if body_params:
            components.append({
                "type": "body",
                "parameters": body_params
            })

        if components:
            template_payload["components"] = components

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_to,
        "type": "template",
        "template": template_payload,
    }

    response_data = _send_meta_request(payload)
    messages = response_data.get("messages", [])
    msg_id = messages[0].get("id") if messages else ""

    return {
        "to": to_number,
        "status": "sent",
        "sid": msg_id,
    }


def send_whatsapp_text(to_number, body):
    """Send a free-form WhatsApp message using Meta Cloud API inside customer service window."""
    _validate_meta_config()

    if not to_number:
        raise ValueError("Recipient WhatsApp number is required.")

    body = str(body or "").strip()
    if not body:
        raise ValueError("Reply message cannot be empty.")

    clean_to = _clean_phone_number(to_number)

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_to,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": body
        }
    }

    response_data = _send_meta_request(payload)
    messages = response_data.get("messages", [])
    msg_id = messages[0].get("id") if messages else ""

    return {
        "to": to_number,
        "status": "sent",
        "sid": msg_id,
    }


def send_bulk_whatsapp_templates(contacts, content_sid, variable_mappings=None):
    """Send an approved template populated with each contact's details."""
    results = []
    variable_mappings = variable_mappings or {}

    for contact in contacts:
        to_number = contact.get("whatsapp_number")

        try:
            contact_variables = _build_content_variables(contact, variable_mappings)
            result = send_whatsapp_template(
                to_number,
                content_sid,
                contact_variables,
            )
            results.append(
                {
                    "name": contact.get("name", ""),
                    "to": to_number,
                    "success": True,
                    "status": result["status"],
                    "sid": result["sid"],
                    "error": "",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "name": contact.get("name", ""),
                    "to": to_number,
                    "success": False,
                    "status": "failed",
                    "sid": "",
                    "error": _format_error(exc),
                }
            )

    return results


def _build_content_variables(contact, variable_mappings):
    content_variables = {}

    for variable_key, mapping in variable_mappings.items():
        resolved_value = _resolve_template_variable(contact, mapping)
        sanitized_value = _sanitize_content_variable_value(resolved_value)

        if sanitized_value == "":
            default_value = _sanitize_content_variable_value(
                mapping.get("default_value", "")
            )
            sanitized_value = default_value

        if sanitized_value != "":
            content_variables[str(variable_key)] = sanitized_value

    return content_variables


def _resolve_template_variable(contact, mapping):
    source_type = mapping.get("source_type", "default")

    if source_type == "contact_field":
        field_name = mapping.get("field_name", "")
        return contact.get(field_name, "")

    if source_type == "custom_text":
        return mapping.get("custom_text", "")

    if source_type == "uploaded_media_url":
        return mapping.get("public_url", "")

    return ""


def _sanitize_content_variable_value(value):
    sanitized_value = str(value or "").replace("\r", " ").replace("\n", " ")
    sanitized_value = sanitized_value.replace("\t", " ")
    sanitized_value = re.sub(r" {5,}", "    ", sanitized_value)
    return sanitized_value.strip()


def _validate_meta_config():
    missing_values = []

    if not WHATSAPP_ACCESS_TOKEN:
        missing_values.append("WHATSAPP_ACCESS_TOKEN")

    if not WHATSAPP_PHONE_NUMBER_ID:
        missing_values.append("WHATSAPP_PHONE_NUMBER_ID")

    if not WHATSAPP_BUSINESS_ACCOUNT_ID:
        missing_values.append("WHATSAPP_BUSINESS_ACCOUNT_ID")

    if missing_values:
        raise ValueError(
            "Missing Meta WhatsApp config value(s): " + ", ".join(missing_values)
        )


def _clean_phone_number(phone_number):
    clean = str(phone_number or "").strip()
    if clean.startswith("whatsapp:"):
        clean = clean.replace("whatsapp:", "", 1)
    clean = re.sub(r"\D", "", clean)
    return clean


def _send_meta_request(payload):
    url = f"https://graph.facebook.com/{META_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    req = Request(url, data=data, headers=headers, method="POST")

    try:
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="ignore")
        err_msg = _extract_meta_error(err_body) or exc.reason
        raise ValueError(f"Meta Cloud API error ({exc.code}): {err_msg}") from exc
    except URLError as exc:
        raise ValueError(f"Unable to reach Meta Cloud API: {exc.reason}") from exc


def _extract_meta_error(response_body):
    if not response_body:
        return ""
    try:
        data = json.loads(response_body)
        if isinstance(data, dict) and "error" in data:
            err = data["error"]
            msg = err.get("message", "")
            details = err.get("error_data", {}).get("details", "")
            return f"{msg} {details}".strip()
    except Exception:
        pass
    return response_body.strip()[:300]


def _format_error(exc):
    return re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).strip()
