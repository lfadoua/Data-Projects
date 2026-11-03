"""Require a source ID and a verbatim supporting quote for every claim."""

from pydantic import BaseModel, ConfigDict, Field


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1200)
    source_id: str = Field(min_length=2, max_length=16)
    quote: str = Field(min_length=20, max_length=2000)


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[Claim] = Field(max_length=2)
    insufficient_evidence: bool


class SummaryClaim(BaseModel):
    """The application owns quotes; a summary can only select an assigned ID."""

    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1200)
    source_id: str = Field(min_length=2, max_length=16)


class GeneratedSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[SummaryClaim] = Field(max_length=2)
    insufficient_evidence: bool
