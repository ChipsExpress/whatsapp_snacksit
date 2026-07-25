import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


load_dotenv()


TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
CONTENT_API_BASE_URL = "https://content.twilio.com/v1"


def fetch_content_template(content_sid):
    """Fetch one Twilio Content template so the UI can map variables safely."""
    _validate_twilio_auth()

    normalized_sid = str(content_sid).strip()
    if not normalized_sid.startswith("HX"):
        raise ValueError("Twilio Content SID must start with HX.")

    url = f"{CONTENT_API_BASE_URL}/Content/{normalized_sid}"
    response = _request_json(url)

    return {
        "sid": response.get("sid", normalized_sid),
        "friendly_name": response.get("friendly_name", ""),
        "language": response.get("language", ""),
        "variables": response.get("variables", {}) or {},
        "types": response.get("types", {}) or {},
    }


def _validate_twilio_auth():
    missing_values = []

    if not TWILIO_ACCOUNT_SID:
        missing_values.append("TWILIO_ACCOUNT_SID")

    if not TWILIO_AUTH_TOKEN:
        missing_values.append("TWILIO_AUTH_TOKEN")

    if missing_values:
        raise ValueError(
            "Missing Twilio config value(s): " + ", ".join(missing_values)
        )


def _request_json(url):
    auth_value = base64.b64encode(
        f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode("utf-8")
    ).decode("ascii")
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {auth_value}",
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
            f"Unable to fetch Twilio template {url.rsplit('/', 1)[-1]}: {message}"
        ) from exc
    except URLError as exc:
        raise ValueError(f"Unable to reach Twilio Content API: {exc.reason}") from exc


def _extract_error_message(response_body):
    if not response_body:
        return ""

    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError:
        return response_body.strip()

    if isinstance(payload, dict):
        return payload.get("message") or payload.get("detail") or ""

    return ""
