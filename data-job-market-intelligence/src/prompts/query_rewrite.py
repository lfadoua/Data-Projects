"""Intent-preserving retrieval normalization; no invented role or location."""

import re

PROMPT_VERSION = "v1"
PROMPT = "Rewrite for retrieval without adding roles, places, seniority, or qualifications."


def rewrite(question: str) -> str:
    text = re.sub(r"\s+", " ", question).strip()
    text = re.sub(r"^(?:hi|hello|hey)[,!]?\s*", "", text, flags=re.I)
    text = re.sub(
        r"^(?:please\s+)?(?:can you|could you|would you|tell me|i want to know)\s+",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"[?!.]+$", "", text).strip()
    # Expand only explicit, unambiguous technology acronyms.
    for short, expanded in {
        "MLOps": "MLOps machine learning operations",
        "NLP": "NLP natural language processing",
    }.items():
        text = re.sub(r"\b" + short + r"\b", expanded, text, flags=re.I)
    lower = text.lower()
    if re.search(r"\b(?:responsibilit|duties|work on)\w*\b", lower):
        text += " responsibilities duties build develop maintain"
    elif re.search(r"\b(?:learn|prepare|skills|know|qualifications)\b", lower):
        text += " required skills qualifications technologies"
    elif re.search(r"\b(?:together|alongside|with)\b", lower) and re.search(
        r"\b(?:technolog|tool|platform)\w*\b", lower
    ):
        text += " related tools technology stack"
    return text
