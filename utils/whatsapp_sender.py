import json
import os
import re

from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException


load_dotenv()


TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")


def send_whatsapp_template(to_number, content_sid, content_variables=None):
    """Send one approved WhatsApp content template using Twilio."""
    _validate_twilio_config()

    if not to_number:
        raise ValueError("Recipient WhatsApp number is required.")

    content_sid = str(content_sid).strip()
    if not content_sid:
        raise ValueError("Twilio Content SID is required.")

    if not content_sid.startswith("HX"):
        raise ValueError("Twilio Content SID must start with HX.")

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    message_payload = {
        "from_": _format_whatsapp_address(TWILIO_WHATSAPP_NUMBER),
        "to": _format_whatsapp_address(to_number),
        "content_sid": content_sid,
    }

    if content_variables:
        message_payload["content_variables"] = json.dumps(content_variables)

    sent_message = client.messages.create(**message_payload)

    return {
        "to": to_number,
        "status": sent_message.status,
        "sid": sent_message.sid,
    }


def send_whatsapp_text(to_number, body):
    """Send a free-form WhatsApp reply inside the active customer service window."""
    _validate_twilio_config()

    if not to_number:
        raise ValueError("Recipient WhatsApp number is required.")

    body = str(body or "").strip()
    if not body:
        raise ValueError("Reply message cannot be empty.")

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    sent_message = client.messages.create(
        from_=_format_whatsapp_address(TWILIO_WHATSAPP_NUMBER),
        to=_format_whatsapp_address(to_number),
        body=body,
    )

    return {
        "to": to_number,
        "status": sent_message.status,
        "sid": sent_message.sid,
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


def _validate_twilio_config():
    missing_values = []

    if not TWILIO_ACCOUNT_SID:
        missing_values.append("TWILIO_ACCOUNT_SID")

    if not TWILIO_AUTH_TOKEN:
        missing_values.append("TWILIO_AUTH_TOKEN")

    if not TWILIO_WHATSAPP_NUMBER:
        missing_values.append("TWILIO_WHATSAPP_NUMBER")

    if missing_values:
        raise ValueError(
            "Missing Twilio config value(s): " + ", ".join(missing_values)
        )


def _format_whatsapp_address(phone_number):
    phone_number = str(phone_number).strip()

    if phone_number.startswith("whatsapp:"):
        return phone_number

    return f"whatsapp:{phone_number}"


def _format_error(exc):
    if isinstance(exc, TwilioRestException):
        code = f" {exc.code}" if exc.code else ""
        return f"Twilio error{code}: {exc.msg}"

    return re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).strip()


