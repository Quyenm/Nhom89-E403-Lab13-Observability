from __future__ import annotations

import hashlib
import re

PII_PATTERNS: dict[str, str] = {
    "jwt_token": r"\beyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\b",
    "api_key": r"\b(?:sk|pk|rk|ak)[_\-][A-Za-z0-9]{16,}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "cccd": r"\b\d{12}\b",
    "passport": r"\b[A-Z]{1,2}\d{6,9}\b",
    "email": r"[\w\.\+\-]+@[\w\.\-]+\.\w{2,}",
    "phone_vn": r"(?:\+84|0)[ \.\-]?\d{3}[ \.\-]?\d{3}[ \.\-]?\d{3,4}",
    "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "vn_address": r"(?i)\b(?:số\s*\d+|phường|quận|huyện|xã|tỉnh|thành phố|tp\.?|đường|ngõ|ngách|thôn|ấp)\b[^,\n]{0,60}",
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
