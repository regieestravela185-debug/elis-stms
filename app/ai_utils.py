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
