"""Rules for obvious quantitative intents; no model calculates market counts."""

import re
from typing import Literal

from pydantic import BaseModel


class RouteDecision(BaseModel):
    route: Literal["analytics", "rag"]
    confidence: float
    reason: str


def classify(question: str) -> RouteDecision:
    quantitative = (
        r"how many|how much|\bcount\b|\btotal\b|percentage|percent|\bproportion\b|"
        r"\bdistribution\b|\bsalary\b|\bsalaries\b|\btrend|\btop\b|"
        r"most (?:requested|common|frequent|jobs)|\bfrequency\b|\bnumber of\b|\bfewest\b|"
        r"\bwhich\b.*\bmost\b|\bwhere\b.*\bmost\b|\bmost\b.*\bpositions\b"
    )
    if re.search(quantitative, question, re.I):
        return RouteDecision(
            route="analytics",
            confidence=0.98,
            reason="The question requests a numerical aggregation.",
        )
    return RouteDecision(
        route="rag",
        confidence=0.75,
        reason="The question requests descriptive job-posting evidence.",
    )
