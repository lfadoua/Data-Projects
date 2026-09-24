"""Validated shared filters and assistant contracts."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    job_title: str | None = Field(default=None, max_length=200)
    seniority: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=300)
    workplace_type: str | None = Field(default=None, max_length=50)
    skill: str | None = Field(default=None, max_length=100)
    topic: str | None = Field(default=None, max_length=100)


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=3, max_length=2000)
    filters: Filters = Field(default_factory=Filters)


class Answer(BaseModel):
    route: Literal["analytics", "rag"]
    answer: str
    data: dict[str, Any] | None = None
    key_points: list[str] = Field(default_factory=list)
    skills: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
