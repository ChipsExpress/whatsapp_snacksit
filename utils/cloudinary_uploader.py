import os

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv


load_dotenv()


def upload_media(file):
    """Upload a Streamlit image file to Cloudinary and return its public URL."""
    _configure_cloudinary()

    upload_bytes = file.getvalue()
    if not upload_bytes:
        raise ValueError("Selected image file is empty.")

    result = cloudinary.uploader.upload(
        upload_bytes,
        resource_type="image",
        folder="whatsapp-bulk-sender",
    )

    secure_url = result.get("secure_url", "").strip()
    if not secure_url:
        raise ValueError("Cloudinary did not return a public URL.")

    return secure_url


def _configure_cloudinary():
    config = {
        "cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME"),
        "api_key": os.getenv("CLOUDINARY_API_KEY"),
        "api_secret": os.getenv("CLOUDINARY_API_SECRET"),
    }
    missing_values = [
        env_name
        for key, env_name in (
            ("cloud_name", "CLOUDINARY_CLOUD_NAME"),
            ("api_key", "CLOUDINARY_API_KEY"),
            ("api_secret", "CLOUDINARY_API_SECRET"),
        )
        if not config[key]
    ]

    if missing_values:
        raise ValueError(
            "Missing Cloudinary config value(s): " + ", ".join(missing_values)
        )

    cloudinary.config(secure=True, **config)
