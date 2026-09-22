import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

META_API_VERSION = "v21.0"


def _get_meta_config():
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    waba_id = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            token = token or st.secrets.get("WHATSAPP_ACCESS_TOKEN", "")
            waba_id = waba_id or st.secrets.get("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
    except Exception:
        pass
    token = (token or "").strip()
    waba_id = (waba_id or "").strip()
    # Correct known typo where '103988149744623' was missing the digit 9 (should be '1093988149744623')
    if waba_id in ("103988149744623", ""):
        waba_id = "1093988149744623"
    return token, waba_id


def fetch_content_template(content_sid):
    """Fetch one Meta WhatsApp Content template so the UI can map variables safely."""
    token, waba_id = _get_meta_config()
    if not token:
        raise ValueError("Missing Meta config value: WHATSAPP_ACCESS_TOKEN")

    normalized_name = str(content_sid).strip()
    if not normalized_name:
        raise ValueError("Template name or ID is required.")

    matched_template = None

    # 1. If content_sid looks like a direct numeric Meta Template ID, query it directly
    if normalized_name.isdigit():
        url_direct = f"https://graph.facebook.com/{META_API_VERSION}/{quote(normalized_name)}"
        try:
            direct_data = _request_meta_json(url_direct, token)
            if isinstance(direct_data, dict) and direct_data.get("name") and "components" in direct_data:
                matched_template = direct_data
        except Exception:
            pass

    # 2. Query WABA message_templates if not found by direct ID
    if not matched_template and waba_id:
        url_by_name = f"https://graph.facebook.com/{META_API_VERSION}/{waba_id}/message_templates?name={quote(normalized_name)}"
        try:
            response = _request_meta_json(url_by_name, token)
            data = response.get("data", [])
        except Exception:
            data = []

        if not data:
            url_all = f"https://graph.facebook.com/{META_API_VERSION}/{waba_id}/message_templates"
            try:
                response = _request_meta_json(url_all, token)
                data = response.get("data", [])
            except Exception:
                data = []

        for item in data:
            if (
                item.get("name", "").lower() == normalized_name.lower()
                or item.get("id") == normalized_name
            ):
                matched_template = item
                break

    if not matched_template:
        raise ValueError(
            f"Template '{normalized_name}' could not be fetched from Meta WhatsApp account. "
            "Please verify that the Template Name or numeric ID is correct and approved in WhatsApp Manager."
        )

    body_text = ""
    variables = {}
    header_info = {}
    components = matched_template.get("components", [])

    for comp in components:
        comp_type = str(comp.get("type", "")).upper()
        if comp_type == "HEADER":
            header_format = comp.get("format", "").upper()
            example_handles = comp.get("example", {}).get("header_handle", [])
            header_url = example_handles[0] if example_handles else ""
            # Meta's internal CDN (scontent.whatsapp.net) gives HTTP 403 Forbidden to its own delivery bots.
            # Fall back to the permanent Cloudinary-hosted Chips Express template banner.
            if not header_url or "scontent.whatsapp.net" in header_url:
                header_url = "https://res.cloudinary.com/ntgkmaw5/image/upload/v1790106878/whatsapp-templates/yi7eufghnyryh7iednqh.png"
            header_info = {
                "format": header_format,
                "url": header_url,
            }
        elif comp_type == "BODY":
            body_text = comp.get("text", "")
            # Extract placeholders like {{1}}, {{2}}
            var_matches = re.findall(r"\{\{(\d+)\}\}", body_text)
            example_values = comp.get("example", {}).get("body_text", [[]])
            first_examples = example_values[0] if example_values else []

            for idx, var_num in enumerate(var_matches):
                if idx < len(first_examples):
                    variables[var_num] = str(first_examples[idx])
                else:
                    variables[var_num] = f"Sample_{var_num}"

    return {
        "sid": matched_template.get("name") or matched_template.get("id", normalized_name),
        "friendly_name": matched_template.get("name", normalized_name),
        "language": matched_template.get("language", "en"),
        "variables": variables,
        "types": {
            "whatsapp/text": {"body": body_text}
        },
        "status": matched_template.get("status", "APPROVED"),
        "category": matched_template.get("category", ""),
        "header": header_info,
    }


def _request_meta_json(url, token):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        message = _extract_error_message(error_body) or exc.reason
        raise ValueError(
            f"Unable to fetch Meta template: {message}"
        ) from exc
    except URLError as exc:
        raise ValueError(f"Unable to reach Meta Graph API: {exc.reason}") from exc


def _extract_error_message(response_body):
    if not response_body:
        return ""

    try:
        payload = json.loads(response_body)
        if isinstance(payload, dict) and "error" in payload:
            return payload["error"].get("message", "")
    except json.JSONDecodeError:
        return response_body.strip()

    return ""

