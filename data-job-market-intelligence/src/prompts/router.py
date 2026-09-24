"""Versioned instruction contract for optional model-based extension."""

PROMPT_VERSION = "v1"
PROMPT = (
    "Choose exactly one route: analytics for counts, percentages, "
    "rankings, salary summaries, and time series; rag for "
    "responsibilities, examples, explanations, and meaning from postings."
    " Never use retrieved snippets to estimate population statistics. If "
    "a question combines both, ask it as two separate questions. Return a"
    " route, confidence, and a short reason, without hidden reasoning."
)
