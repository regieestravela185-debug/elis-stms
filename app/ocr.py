from __future__ import annotations

import re
import time
import base64
from pathlib import Path


# Valid ID types that match the form dropdown
VALID_ID_TYPES = {
    "National ID",
    "UMID", 
    "PhilHealth",
    "Driver's License",
    "Passport",
    "SSS",
    "Postal ID",
    "PRC ID",
    "Voter's ID",
    "TIN ID",
    "Other"
}


def _detect_id_type(text: str) -> str:
    """
    Detect ID type from OCR text with strict validation.
    Only returns a type if there's strong evidence in the text.
    Returns empty string if no valid ID type is detected.
    """
    t = text.lower()

    def word(*terms):
        """Match a short acronym as a word, not as a run of letters.

        "lto" in t was true for "alto" and "Malto"; "prc" for "prcinct";
        "sss" for any triple s. Each of those quietly relabelled somebody's
        ID as a different one.
        """
        return any(re.search(rf"\b{re.escape(w)}\b", t) for w in terms)

    # National ID. The card itself says PHILIPPINE IDENTIFICATION CARD —
    # the phrase "national id" appears nowhere on it, which is why a real
    # PhilID was never recognised.
    if (any(k in t for k in ["philippine identification", "pambansang pagkakakilanlan",
                             "philsys", "national id", "pambansang"])
            or (word("pcn", "psn") and "pilipinas" in t)):
        return "National ID"

    # PhilHealth
    if "philhealth" in t or ("philippine health" in t and "insurance" in t):
        return "PhilHealth"

    # Driver's License
    if ("driver" in t and "licen" in t) or word("lto") or "land transportation" in t:
        return "Driver's License"
    
    # Passport - require multiple indicators
    passport_indicators = ["passport", "republic of the philippines", "p<phl", "department of foreign affairs"]
    passport_count = sum(1 for indicator in passport_indicators if indicator in t)
    if passport_count >= 2:  # Require at least 2 indicators
        return "Passport"
    
    # UMID must be tested before SSS. Every UMID card carries the words
    # SOCIAL SECURITY SYSTEM, because SSS issues it — so with SSS first, a
    # UMID was always answered as an SSS card.
    if word("umid") or "unified multi-purpose" in t:
        return "UMID"

    # SSS
    if "social security" in t or (word("sss") and "number" in t):
        return "SSS"
    
    # Postal ID
    if "postal" in t and "id" in t:
        return "Postal ID"
    
    # PRC ID
    if word("prc") or "professional regulation" in t:
        return "PRC ID"
    
    # Voter's ID
    if "voter" in t or "comelec" in t or ("commission" in t and "elections" in t):
        return "Voter's ID"
    
    # TIN ID
    if (word("tin") and ("id" in t or "number" in t)) or "bureau of internal revenue" in t:
        return "TIN ID"
    
    # If no specific ID type detected, return empty string (not "Other")
    # User must manually select the ID type
    return ""


def _extract_id_number(text: str) -> str:
    # Keep this conservative: capture long alnum token or grouped number patterns.
    # Avoid common words like "Republic", "Number", "License", etc.
    patterns = [
        r"\b\d{2}[-\s]\d{9}[-\s]\d{1}\b",  # PhilHealth ID: 08-051636356-1
        r"\b[A-Z]\d{2}[-\s]\d{2}[-\s]\d{6}\b",  # PH Driver's License: D12-24-004398
        r"\b\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b",  # Credit card style
        r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b",  # SSN style
        r"\b[A-Z]{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Driver's license pattern (alternative)
        r"\b[A-Z]{1,2}\d{7,12}\b",  # ID pattern (letters followed by numbers)
        r"\b\d{10,16}\b",  # Long pure numbers
        r"\b\d{4}[-\s]\d{4}[-\s]\d{4}\b",  # Generic 12-digit grouped
        r"\b\d{3}[-\s]\d{7}\b",  # SSS-like pattern
        r"\b\d{12}\b",  # 12-digit plain
        # Added after checking each type in the dropdown against the text
        # actually printed on it — these four were read as nothing at all,
        # which sent every one of them to manual review.
        r"\b\d{2}[-\s]\d{7}[-\s]\d{1}\b",       # SSS: 03-1234567-8
        r"\b\d{3}[-\s]\d{3}[-\s]\d{3}[-\s]\d{3}\b",  # TIN: 123-456-789-000
        r"\b[A-Z]\d{7}[A-Z]?\b",                  # Passport: P1234567A
        r"\b\d{4}[-\s]\d{7}[-\s]\d{1}\b",       # UMID CRN: 0111-2233445-6
        r"\b\d{7}\b",                            # PRC registration: 0123456
    ]

    # Common words to exclude
    exclude_words = {"republic", "number", "license", "identification", "card", "philippines", "of", "the"}

    for p in patterns:
        matches = re.findall(p, text, flags=re.IGNORECASE)
        for match in matches:
            normalized = match.lower().replace("-", "").replace(" ", "")
            # Check if it's not a common word and has enough digits
            if normalized not in exclude_words and sum(c.isdigit() for c in normalized) >= 6:
                return match.strip()
    return ""


# What the reader is told when the scan does not work. Short, and about
# what they can do next — never about sockets or SSL.
UNREADABLE = ("Could not read this photo. Choose the ID type below and type "
              "the number, or try a clearer picture.")
OFFLINE = ("The ID scanner is not responding right now. Choose the ID type "
           "below and type the number — your reservation will still go "
           "through, and staff will check the photo.")


def _log(msg, *args):
    try:
        from flask import current_app
        current_app.logger.warning(msg, *args)
    except Exception:
        pass


def _ocr_api_key() -> str:
    """The OCR.space key, from config when one is set."""
    try:
        from flask import current_app
        key = (current_app.config.get("OCR_SPACE_API_KEY") or "").strip()
        if key:
            return key
        current_app.logger.warning(
            "OCR_SPACE_API_KEY is not set — falling back to the shared demo "
            "key, which usually returns nothing. Register a free key at "
            "ocr.space and set it in the environment."
        )
    except Exception:
        pass
    return "helloworld"


def scan_id_fields(file_path: str | Path) -> dict[str, str]:
    """
    Best-effort OCR extractor using OCR.space API.
    Returns empty fields when OCR API is unavailable or fails.
    Now with stricter validation - only returns ID type if confident.
    """
    path = Path(file_path)
    try:
        import requests  # type: ignore
    except Exception:
        return {
            "id_type": "",
            "id_number": "",
            "ocr_note": "OCR API library (requests) is not installed.",
        }

    try:
        raw = path.read_bytes()

        # OCR.space's free tier refuses anything over 1 MB. A photo from a
        # phone is several times that, so it is drawn down here rather than
        # sent and rejected — the text on an ID stays legible well below the
        # limit, and this is also the only path a file-picker upload takes.
        if len(raw) > 900_000:
            try:
                from PIL import Image
                import io as _io
                im = Image.open(_io.BytesIO(raw))
                im.thumbnail((1800, 1800))
                buf = _io.BytesIO()
                im.convert("RGB").save(buf, format="JPEG", quality=82, optimize=True)
                raw = buf.getvalue()
            except Exception:
                pass                       # send the original and let the API decide

        # The prefix has to name the format actually being sent. It said PNG
        # for every upload, including the JPEGs that phones produce.
        ext = path.suffix.lower().lstrip(".") or "jpg"
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png",
                "webp": "webp", "gif": "gif", "pdf": "pdf"}.get(ext, "jpeg")
        image_data = base64.b64encode(raw).decode()

        # Call OCR.space API
        def _call():
            return requests.post(
                "https://api.ocr.space/parse/image",
                timeout=25,                # never let a hung call hold a worker
                data={
                    "base64Image": f"data:image/{mime};base64,{image_data}",
                    "language": "eng",
                    "isOverlayRequired": False,
                    "scale": True,
                    "detectOrientation": True,
                    "OCREngine": "2",
                },
            # "helloworld" is OCR.space's public demo key: rate-limited to a
            # handful of calls and shared with everyone on the internet, so
            # it returns nothing most of the time. Set OCR_SPACE_API_KEY to
            # a free registered key and OCR starts working; the demo key is
            # kept only so a local run does not hard-fail.
                headers={"apikey": _ocr_api_key()},
            )

        # One retry. The failure reported from the field was an SSL timeout
        # reaching api.ocr.space — a transient network fault, nothing to do
        # with the photo, and it left the reader typing everything by hand.
        try:
            response = _call()
        except Exception:
            time.sleep(1.5)
            response = _call()

        result = response.json()

        if result.get("IsErroredOnProcessing", False):
            _log("OCR service error: %s", result.get("ErrorMessage", "unknown"))
            return {"id_type": "", "id_number": "", "ocr_note": UNREADABLE}

        if not result.get("ParsedResults"):
            _log("OCR returned no parsed results")
            return {"id_type": "", "id_number": "", "ocr_note": UNREADABLE}

        text = result["ParsedResults"][0].get("ParsedText", "")
    except Exception as exc:
        # The technical detail belongs in the log, not on the screen. This
        # used to hand the reader a raw Python traceback string —
        # "HTTPSConnectionPool(host='api.ocr.space'... SSLError" — which
        # tells them nothing they can act on.
        _log("OCR request failed: %s", exc)
        return {"id_type": "", "id_number": "", "ocr_note": OFFLINE}

    if not text.strip():
        return {"id_type": "", "id_number": "", "ocr_note": UNREADABLE}

    detected_type = _detect_id_type(text)
    
    # Validation note
    if not detected_type:
        ocr_note = "Could not identify valid ID type. Please select manually."
    else:
        ocr_note = f"Detected as {detected_type}"

    return {
        "id_type": detected_type,  # Will be empty string if not confident
        "id_number": _extract_id_number(text),
        "ocr_note": ocr_note,
    }
