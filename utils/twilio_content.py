import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")

META_API_VERSION = "v21.0"


def fetch_content_template(content_sid):
    """Fetch one Meta WhatsApp Content template so the UI can map variables safely."""
    _validate_meta_auth()

    normalized_name = str(content_sid).strip()
    if not normalized_name:
        raise ValueError("Template name or ID is required.")

    # Try fetching by name filter first
    url = f"https://graph.facebook.com/{META_API_VERSION}/{WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates?name={quote(normalized_name)}"
    
    try:
        response = _request_meta_json(url)
        data = response.get("data", [])
    except Exception:
        data = []

    # If not found by name parameter, fetch all templates and search
    if not data:
        url_all = f"https://graph.facebook.com/{META_API_VERSION}/{WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates"
        response = _request_meta_json(url_all)
        data = response.get("data", [])

    matched_template = None
    for item in data:
        if (
            item.get("name", "").lower() == normalized_name.lower()
            or item.get("id") == normalized_name
        ):
            matched_template = item
            break

    if not matched_template:
        if data and not normalized_name:
            matched_template = data[0]
        else:
            available_names = ", ".join([t.get("name", "") for t in data[:5]]) if data else "none"
            raise ValueError(
                f"Template '{normalized_name}' not found in Meta WhatsApp account. "
                f"Available templates: {available_names}"
            )

    body_text = ""
    variables = {}
    components = matched_template.get("components", [])

    for comp in components:
        comp_type = str(comp.get("type", "")).upper()
        if comp_type == "BODY":
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
        "language": matched_template.get("language", "en_US"),
        "variables": variables,
        "types": {
            "whatsapp/text": {"body": body_text}
        },
        "status": matched_template.get("status", "APPROVED"),
        "category": matched_template.get("category", ""),
    }


def _validate_meta_auth():
    missing_values = []

    if not WHATSAPP_BUSINESS_ACCOUNT_ID:
        missing_values.append("WHATSAPP_BUSINESS_ACCOUNT_ID")

    if not WHATSAPP_ACCESS_TOKEN:
        missing_values.append("WHATSAPP_ACCESS_TOKEN")

    if missing_values:
        raise ValueError(
            "Missing Meta config value(s): " + ", ".join(missing_values)
        )


def _request_meta_json(url):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
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
