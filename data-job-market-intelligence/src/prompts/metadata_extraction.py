"""Versioned instruction contract for optional model-based extension."""

PROMPT_VERSION = "v1"
PROMPT = (
    "Extract only explicitly stated or unambiguously named job_title, "
    "seniority, country, city, company, workplace_type, skill, and topic."
    " Every field is optional. Do not substitute a search location for a "
    "job location. When several values compete or you are unsure, use "
    "null. Return validated JSON fields only."
)
