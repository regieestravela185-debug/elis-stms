"""What a submitted file is allowed to be.

The upload fields carried an `accept` attribute and nothing else. That
attribute is a hint the file picker follows and an attacker ignores: the
browser can be told to send anything, so a .exe or .svg renamed .jpg, or
simply chosen through a scripted request, was stored and served back.

Three things are checked here, because each catches what the others
miss: the extension (what the file claims), the browser's content type
(what the client says it is), and the leading bytes of the file itself
(what it actually is). A file passes only if all three agree.
"""
from __future__ import annotations

import os

# Real leading bytes for the formats accepted anywhere in the app. Magic
# numbers are the only one of the three signals a caller cannot simply
# assert, which is why an image upload must match one.
_SIGNATURES = {
    "jpg":  [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png":  [b"\x89PNG\r\n\x1a\n"],
    "webp": [b"RIFF"],          # plus "WEBP" at offset 8, checked below
    "gif":  [b"GIF87a", b"GIF89a"],
    "pdf":  [b"%PDF-"],
}

IMAGE_TYPES = ("jpg", "jpeg", "png", "webp", "gif")
DOCUMENT_TYPES = IMAGE_TYPES + ("pdf",)

_CONTENT_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "gif": "image/gif", "pdf": "application/pdf",
}

# 8 MB. Large enough for a phone photo of an ID, small enough that a
# careless upload does not fill the request or the storage bucket.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


def _extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lstrip(".").lower()


def _looks_like(head: bytes, kind: str) -> bool:
    if kind == "webp":
        return head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    return any(head.startswith(sig) for sig in _SIGNATURES.get(kind, []))


def validate_upload(file_storage, allowed=IMAGE_TYPES, *, label="file",
                    max_bytes=MAX_UPLOAD_BYTES):
    """Return (ok, message). The message is written for the person
    uploading, not for a log."""
    if file_storage is None or not getattr(file_storage, "filename", ""):
        return False, f"Please choose a {label}."

    ext = _extension(file_storage.filename)
    pretty = ", ".join(e.upper() for e in allowed)
    if ext not in allowed:
        return False, (f"That {label} is a .{ext or 'unknown'} file. "
                       f"Please upload one of: {pretty}.")

    # Read the head, then rewind so the caller still gets a whole file.
    stream = file_storage.stream
    try:
        stream.seek(0)
        head = stream.read(16)
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(0)
    except Exception:
        return False, f"That {label} could not be read. Please try again."

    if size == 0:
        return False, f"That {label} is empty."
    if size > max_bytes:
        return False, (f"That {label} is {size / 1048576:.1f} MB. "
                       f"The largest allowed is {max_bytes // 1048576} MB.")

    if not _looks_like(head, ext):
        # The name says one thing and the bytes say another — the case a
        # renamed file is meant to slip through.
        return False, (f"That {label} does not look like a real .{ext} "
                       f"file. Please upload the original photo or scan.")

    declared = (getattr(file_storage, "content_type", "") or "").split(";")[0].strip()
    if declared and declared != _CONTENT_TYPES.get(ext):
        return False, (f"That {label} was sent as {declared}, which does not "
                       f"match a .{ext} file.")

    return True, ""
