"""Require a source ID and a verbatim supporting quote for every claim."""

from pydantic import BaseModel, ConfigDict


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    source_id: str
    quote: str


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[Claim]
    insufficient_evidence: bool
