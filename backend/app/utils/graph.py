from __future__ import annotations

from typing import Optional


def canonicalize_actor(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    lower_text = text.lower()
    if lower_text.startswith("tel:"):
        text = text[4:]
        lower_text = text.lower()

    if "@" in text:
        return lower_text

    digits = [char for char in text if char.isdigit()]
    if digits:
        prefix = "+" if text.strip().startswith("+") else ""
        return prefix + "".join(digits)

    return lower_text


def compose_display_name(given_name: Optional[str], family_name: Optional[str]) -> Optional[str]:
    parts = [given_name, family_name]
    filtered = [str(part).strip() for part in parts if part]
    return " ".join(filtered) if filtered else None
