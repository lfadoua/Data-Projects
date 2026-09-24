"""Conservative text cleaning without inventing missing content."""

import html
import re


def clean_text(value: str | None) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", text, flags=re.I | re.S)
    text = re.sub(r"<(?:br|/p|/div|/li)\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text).replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(
        re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines() if line.strip()
    ).strip()
