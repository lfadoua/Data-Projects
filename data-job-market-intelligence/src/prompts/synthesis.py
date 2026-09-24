"""Versioned instruction contract for optional model-based extension."""

PROMPT_VERSION = "v1"
PROMPT = (
    "Combine an exact SQL result and source-grounded text only when both "
    "are available. Label the SQL population and its filters; cite every "
    "descriptive claim with a retrieved source ID. Never infer a global "
    "percentage from examples. If only one route ran, leave the other "
    "component out instead of inventing it."
)
