"""Paragraph/sentence aware chunks, with a bounded word-based fallback.

Size is measured in words (450 words approximates 600 tokens for English).
Only sentences longer than the budget are split on word boundaries.
"""

import re


def chunk_text(text: str, size: int = 450, overlap: int = 60) -> list[str]:
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > overlap >= 0")
    units = []
    for paragraph in re.split(r"\n+", text.strip()):
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph.strip()):
            words = sentence.split()
            if len(words) <= size:
                if words:
                    units.append(sentence)
            else:
                units.extend(" ".join(words[i : i + size]) for i in range(0, len(words), size))
    chunks, current = [], []
    for unit in units:
        count = sum(len(part.split()) for part in current)
        if current and count + len(unit.split()) > size:
            chunks.append("\n".join(current))
            tail, tail_count = [], 0
            for part in reversed(current):
                n = len(part.split())
                if tail_count + n > overlap:
                    break
                tail.insert(0, part)
                tail_count += n
            current = tail
            while current and sum(len(p.split()) for p in current) + len(unit.split()) > size:
                current.pop(0)
        current.append(unit)
    if current:
        last = "\n".join(current)
        if not chunks or last != chunks[-1]:
            chunks.append(last)
    return chunks
