from __future__ import annotations

import re
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
    
    # Count confidence indicators for each ID type
    # National ID
    if any(keyword in t for keyword in ["national id", "philsys", "pambansang", "republic of the philippines id"]):
        return "National ID"
    
    # PhilHealth
    if "philhealth" in t or ("philippine health" in t and "insurance" in t):
        return "PhilHealth"
    
    # Driver's License
    if ("driver" in t and "license" in t) or "lto" in t or "land transportation office" in t:
        return "Driver's License"
    
    # Passport - require multiple indicators
    passport_indicators = ["passport", "republic of the philippines", "p<phl", "department of foreign affairs"]
    passport_count = sum(1 for indicator in passport_indicators if indicator in t)
    if passport_count >= 2:  # Require at least 2 indicators
        return "Passport"
    
    # SSS
    if "social security" in t or ("sss" in t and "number" in t):
        return "SSS"
    
    # UMID
    if "umid" in t or "unified multi-purpose id" in t:
        return "UMID"
    
    # Postal ID
    if "postal" in t and "id" in t:
        return "Postal ID"
    
    # PRC ID
    if "prc" in t or "professional regulation commission" in t:
        return "PRC ID"
    
    # Voter's ID
    if "voter" in t or "comelec" in t or ("commission" in t and "elections" in t):
        return "Voter's ID"
    
    # TIN ID
    if ("tin" in t and ("id" in t or "number" in t)) or "bureau of internal revenue" in t:
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
        # Read and encode image
        with open(path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        # Call OCR.space API (free tier)
        response = requests.post(
            "https://api.ocr.space/parse/image",
            data={
                "base64Image": f"data:image/png;base64,{image_data}",
                "language": "eng",
                "isOverlayRequired": False,
                "scale": True,
                "detectOrientation": True,
                "OCREngine": "2",
            },
            headers={"apikey": "helloworld"},  # Free API key
        )
        result = response.json()

        if result.get("IsErroredOnProcessing", False):
            return {"id_type": "", "id_number": "", "ocr_note": f"OCR API error: {result.get('ErrorMessage', 'Unknown error')}"}

        if not result.get("ParsedResults"):
            return {"id_type": "", "id_number": "", "ocr_note": "OCR API returned no results."}

        text = result["ParsedResults"][0].get("ParsedText", "")
    except Exception as e:
        return {"id_type": "", "id_number": "", "ocr_note": f"OCR API request failed: {str(e)}"}

    if not text.strip():
        return {"id_type": "", "id_number": "", "ocr_note": "OCR found no readable text."}

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
