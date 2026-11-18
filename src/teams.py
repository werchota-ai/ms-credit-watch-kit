"""Teams outgoing webhook: verify the HMAC signature and read the command."""
from __future__ import annotations

import base64
import hashlib
import hmac
import re

COMMANDS = {
    "daily": "daily", "day": "daily", "today": "daily", "täglich": "daily", "tag": "daily", "heute": "daily",
    "weekly": "weekly", "week": "weekly", "woche": "weekly", "wöchentlich": "weekly",
    "monthly": "monthly", "month": "monthly", "monat": "monthly", "monatlich": "monthly",
    "status": "full", "full": "full", "now": "full", "jetzt": "full",
    "help": "help", "hilfe": "help", "?": "help",
}


def verify(secret_b64: str, body: bytes, auth_header: str | None) -> bool:
    """Teams signs the raw body with HMAC-SHA256 using the secret shown when the webhook was created."""
    if not secret_b64 or not auth_header or not auth_header.startswith("HMAC "):
        return False
    try:
        key = base64.b64decode(secret_b64)
    except Exception:  # noqa: BLE001
        return False
    expected = base64.b64encode(hmac.new(key, body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, auth_header[5:].strip())


def command(activity: dict) -> str:
    """'<at>Credit Watch</at> weekly' -> 'weekly'; unknown text -> 'help'."""
    text = re.sub(r"<at>.*?</at>", " ", activity.get("text") or "", flags=re.S)
    text = re.sub(r"<[^>]+>|&nbsp;", " ", text).strip().lower()
    for word in text.split():
        if word in COMMANDS:
            return COMMANDS[word]
    return "help" if text else "full"


def who(activity: dict) -> str:
    return ((activity.get("from") or {}).get("name") or "").strip()
