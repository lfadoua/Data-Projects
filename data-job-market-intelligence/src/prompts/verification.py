"""Versioned instruction contract for optional model-based extension."""

PROMPT_VERSION = "v1"
PROMPT = (
    "Before presenting a claim, require a source ID from the supplied "
    "evidence and an exact supporting quote inside that source chunk. "
    "Reject unknown IDs, mismatched quotes, fabricated URLs, unsupported "
    "statistics, or a claim stronger than the quotation. If no claims "
    "remain, explicitly say the evidence is insufficient."
)
