"""
Lightweight, dependency-free AI helpers (rule/heuristic based — no external
LLM, no API key, no cost). Covers:

  - analyze_sentiment(text, rating)      -> feedback sentiment
  - suggest_reply(kind, category, text)  -> draft reply for concerns/inquiries
  - churn_score(...)                     -> renewal/churn risk heuristic

Bilingual (English + Tagalog) lexicons so it works for local feedback.
"""
from __future__ import annotations

import re
from typing import Optional

# --- Sentiment lexicons (lowercase, English + Tagalog) ---
_POSITIVE = {
    "good", "great", "excellent", "amazing", "satisfied", "happy", "clean",
    "helpful", "fast", "quick", "friendly", "nice", "love", "loved", "comfortable",
    "safe", "secure", "recommend", "recommended", "thank", "thanks", "wonderful",
    "perfect", "best", "affordable", "responsive", "accommodating", "smooth",
    "maganda", "mabait", "malinis", "mabilis", "masaya", "salamat", "ayos",
    "magaling", "maayos", "sulit", "presko", "maaliwalas",
}
_NEGATIVE = {
    "bad", "poor", "slow", "dirty", "rude", "broken", "leak", "leaking", "noisy",
    "noise", "delay", "delayed", "problem", "issue", "issues", "unhappy",
    "disappointed", "disappointing", "expensive", "terrible", "worst", "horrible",
    "unsafe", "smell", "smelly", "damaged", "unresponsive", "ignored", "late",
    "hindi", "ayaw", "sira", "sirang", "mabagal", "marumi", "mabaho", "ingay",
    "mahal", "reklamo", "problema", "pangit", "bastos", "delayed", "matagal",
}
_INTENSIFIERS = {"very", "super", "sobra", "sobrang", "grabe", "napaka", "really"}


def _tokens(text: str):
    return re.findall(r"[a-zA-ZñÑáéíóúàèìòù]+", (text or "").lower())


def analyze_sentiment(text: str, rating: Optional[int] = None) -> dict:
    """Return {'label': positive|neutral|negative, 'score': float, 'flag': bool}.

    Combines a bilingual word-lexicon score with the star rating (if any).
    'flag' marks feedback that likely needs admin follow-up.
    """
    toks = _tokens(text)
    score = 0.0
    boost = 1.0
    for w in toks:
        if w in _INTENSIFIERS:
            boost = 1.6
            continue
        if w in _POSITIVE:
            score += 1.0 * boost
        elif w in _NEGATIVE:
            score -= 1.0 * boost
        boost = 1.0

    # Blend in the star rating when present (rating dominates strong signals).
    if rating is not None:
        try:
            r = int(rating)
            if r <= 2:
                score -= 2.0
            elif r == 3:
                score -= 0.3
            elif r >= 4:
                score += 1.5
        except (TypeError, ValueError):
            pass

    if score > 0.5:
        label = "positive"
    elif score < -0.5:
        label = "negative"
    else:
        label = "neutral"

    flag = label == "negative" or (rating is not None and _safe_int(rating) is not None and _safe_int(rating) <= 2)
    return {"label": label, "score": round(score, 2), "flag": bool(flag)}


def _safe_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# --- Reply suggestions (template based) ---
_REPLY_TEMPLATES = {
    "maintenance": (
        "Thank you for reporting this. Our maintenance team has been notified and "
        "will schedule a visit as soon as possible. We'll keep you updated on the "
        "status and appreciate your patience."
    ),
    "billing": (
        "Thank you for reaching out regarding your billing concern. We're reviewing "
        "your account details and will get back to you with a clear breakdown shortly. "
        "Please let us know if you have any questions in the meantime."
    ),
    "payment": (
        "Thank you for your message about your payment. We're verifying the details on "
        "our end and will confirm your record shortly. We'll reach out if we need any "
        "additional information."
    ),
    "noise": (
        "Thank you for letting us know. We take concerns about noise seriously and will "
        "coordinate with the parties involved to address this promptly."
    ),
    "security": (
        "Thank you for raising this security concern. Your safety is our priority — we're "
        "looking into it right away and will update you on the steps we're taking."
    ),
    "general": (
        "Thank you for reaching out to The Elis Center. We've received your message and "
        "our team will review it and respond as soon as possible. We appreciate your patience."
    ),
}


def suggest_reply(category: Optional[str] = None, text: str = "") -> str:
    """Return a professional draft reply based on category/keywords (no LLM)."""
    cat = (category or "").strip().lower()
    if cat in _REPLY_TEMPLATES:
        return _REPLY_TEMPLATES[cat]
    body = (text or "").lower()
    for key in ("maintenance", "repair", "leak", "aircon", "water", "electric"):
        if key in body:
            return _REPLY_TEMPLATES["maintenance"]
    for key in ("bill", "charge", "billing"):
        if key in body:
            return _REPLY_TEMPLATES["billing"]
    for key in ("pay", "payment", "deposit", "receipt"):
        if key in body:
            return _REPLY_TEMPLATES["payment"]
    for key in ("noise", "loud", "ingay"):
        if key in body:
            return _REPLY_TEMPLATES["noise"]
    for key in ("security", "safety", "theft", "cctv"):
        if key in body:
            return _REPLY_TEMPLATES["security"]
    return _REPLY_TEMPLATES["general"]


WATER_BILL_RATES = {
    "1-2": 205.0,
    "3-4": 305.0,
    "5-6": 405.0,
}


_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety",
]


def _three_digits_to_words(n: int) -> str:
    if n == 0:
        return ""
    words = []
    if n >= 100:
        words.append(_ONES[n // 100] + " Hundred")
        n %= 100
    if n >= 20:
        words.append(_TENS[n // 10])
        n %= 10
        if n:
            words.append(_ONES[n])
    elif n > 0:
        words.append(_ONES[n])
    return " ".join(words)


def amount_to_words(amount) -> str:
    """Peso amount -> words, for legal document boilerplate (e.g. lease
    contracts) that spell out amounts alongside the numeral — matches the
    convention in the property's existing lease contract template."""
    amount = float(amount)
    pesos = int(amount)
    centavos = round((amount - pesos) * 100)

    if pesos == 0:
        peso_words = "Zero"
    else:
        parts = []
        for divisor, label in ((1_000_000_000, "Billion"), (1_000_000, "Million"), (1_000, "Thousand"), (1, "")):
            chunk, pesos = divmod(pesos, divisor) if divisor > 1 else (pesos, 0)
            if chunk:
                chunk_words = _three_digits_to_words(chunk)
                parts.append(f"{chunk_words} {label}".strip())
        peso_words = " ".join(parts)

    result = f"{peso_words} Pesos"
    if centavos:
        result += f" and {_three_digits_to_words(centavos)} Centavos"
    return result


def compute_water_bill(pax_range: Optional[str]) -> Optional[float]:
    """Fixed monthly water bill for a residential unit, by occupant-count
    bracket. Commercial units pay their own water bill directly and don't
    use this. Returns None if the unit has no pax_range set yet."""
    return WATER_BILL_RATES.get(pax_range)


def churn_score(days_to_expiry: Optional[int], late_payments: int = 0,
                open_concerns: int = 0, avg_rating: Optional[float] = None) -> dict:
    """Heuristic renewal/churn risk. Returns {'score':0-100,'level','reasons':[...]}.

    Higher score = higher risk of NOT renewing.
    """
    score = 0
    reasons = []

    if days_to_expiry is not None:
        if days_to_expiry <= 30:
            score += 25; reasons.append("Contract expiring within 30 days")
        elif days_to_expiry <= 60:
            score += 12; reasons.append("Contract expiring within 60 days")

    if late_payments >= 3:
        score += 30; reasons.append(f"{late_payments} late payments")
    elif late_payments > 0:
        score += 12; reasons.append(f"{late_payments} late payment(s)")

    if open_concerns >= 2:
        score += 25; reasons.append(f"{open_concerns} unresolved concerns")
    elif open_concerns == 1:
        score += 12; reasons.append("1 unresolved concern")

    if avg_rating is not None:
        if avg_rating <= 2.5:
            score += 20; reasons.append(f"Low satisfaction ({avg_rating}/5)")
        elif avg_rating <= 3.5:
            score += 8; reasons.append(f"Moderate satisfaction ({avg_rating}/5)")

    score = min(100, score)
    level = "high" if score >= 55 else "medium" if score >= 25 else "low"
    if not reasons:
        reasons.append("No risk signals detected")
    return {"score": score, "level": level, "reasons": reasons}
