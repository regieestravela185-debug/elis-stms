"""
Supabase Storage helper.

Uploads files to a Supabase Storage bucket via the Storage REST API using the
`requests` library (no extra dependency). This gives us *persistent* file
storage — unlike the local filesystem on Render, which is ephemeral and wiped
on every deploy/restart.

Enable by setting these env vars (see .env.example):
    SUPABASE_URL          e.g. https://xxxxxxxx.supabase.co
    SUPABASE_SERVICE_KEY  the service_role key (Settings -> API)
    SUPABASE_BUCKET       the (public) bucket name, default "unit-images"

If the env vars are not set, is_enabled() returns False and callers should fall
back to local storage (useful for local development).
"""
from __future__ import annotations

import logging
import mimetypes

import requests
from flask import current_app

logger = logging.getLogger(__name__)

# How long to wait for Supabase Storage HTTP calls (seconds).
_TIMEOUT = 30


def is_enabled() -> bool:
    """True when Supabase Storage is configured."""
    return bool(
        current_app.config.get("SUPABASE_URL")
        and current_app.config.get("SUPABASE_SERVICE_KEY")
    )


def _headers(content_type: str, upsert: bool = True) -> dict:
    key = current_app.config["SUPABASE_SERVICE_KEY"]
    return {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": content_type,
        # x-upsert lets us overwrite an existing object at the same path.
        "x-upsert": "true" if upsert else "false",
    }


def public_url(dest_path: str) -> str:
    """Return the public URL for an object already stored in the bucket."""
    base = current_app.config["SUPABASE_URL"]
    bucket = current_app.config["SUPABASE_BUCKET"]
    return f"{base}/storage/v1/object/public/{bucket}/{dest_path.lstrip('/')}"


def upload_bytes(data: bytes, dest_path: str, content_type: str | None = None) -> str:
    """
    Upload raw bytes to `dest_path` inside the configured bucket and return the
    public URL. Raises on failure.
    """
    base = current_app.config["SUPABASE_URL"]
    bucket = current_app.config["SUPABASE_BUCKET"]
    dest_path = dest_path.lstrip("/")

    if not content_type:
        content_type = mimetypes.guess_type(dest_path)[0] or "application/octet-stream"

    url = f"{base}/storage/v1/object/{bucket}/{dest_path}"
    resp = requests.post(
        url, data=data, headers=_headers(content_type), timeout=_TIMEOUT
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Supabase upload failed ({resp.status_code}): {resp.text[:300]}"
        )
    return public_url(dest_path)


def upload_local_file(local_path, dest_path: str):
    """Upload an already-saved local file to `dest_path`.

    Returns the public URL when Supabase Storage is enabled, otherwise None
    (so callers can fall back to the local relative path). Never raises — a
    storage hiccup shouldn't break an upload flow; it just falls back to local.
    """
    if not is_enabled():
        return None
    try:
        with open(local_path, "rb") as f:
            data = f.read()
        return upload_bytes(data, dest_path)
    except Exception as e:  # pragma: no cover
        logger.warning("Supabase upload_local_file failed (%s): %s", dest_path, e)
        return None


def upload_file_storage(file_storage, dest_path: str) -> str:
    """
    Upload a Werkzeug FileStorage (request.files item) to `dest_path` and return
    the public URL.
    """
    data = file_storage.read()
    content_type = (
        getattr(file_storage, "content_type", None)
        or mimetypes.guess_type(dest_path)[0]
        or "application/octet-stream"
    )
    return upload_bytes(data, dest_path, content_type)


def delete_file(dest_path: str) -> bool:
    """Delete an object from the bucket by its storage path. Never raises."""
    if not is_enabled():
        return False
    base = current_app.config["SUPABASE_URL"]
    bucket = current_app.config["SUPABASE_BUCKET"]
    dest_path = dest_path.lstrip("/")
    url = f"{base}/storage/v1/object/{bucket}/{dest_path}"
    try:
        resp = requests.delete(url, headers=_headers("application/json"), timeout=_TIMEOUT)
        if resp.status_code not in (200, 204):
            logger.warning("Supabase delete failed (%s) for %s: %s", resp.status_code, dest_path, resp.text[:300])
            return False
        return True
    except Exception as e:  # pragma: no cover
        logger.warning("Supabase delete_file failed (%s): %s", dest_path, e)
        return False


def delete_public_url(file_url: str) -> bool:
    """Delete an object given the full public URL stored on a model (as
    returned by upload_local_file/upload_bytes). No-op (returns False) if the
    URL doesn't point at our configured bucket, e.g. a local relative path.
    """
    if not is_enabled() or not file_url:
        return False
    prefix = f"{current_app.config['SUPABASE_URL']}/storage/v1/object/public/{current_app.config['SUPABASE_BUCKET']}/"
    if not file_url.startswith(prefix):
        return False
    return delete_file(file_url[len(prefix):])
