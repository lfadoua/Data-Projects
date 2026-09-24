"""Structured jobs, normalized skills and source-linked pgvector chunks."""

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.config.settings import get_settings


class Base(DeclarativeBase):
    """Shared SQLAlchemy metadata."""


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    job_title: Mapped[str] = mapped_column(Text)
    normalized_job_title: Mapped[str] = mapped_column(String(100), index=True)
    company: Mapped[str | None] = mapped_column(Text, index=True)
    location: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(100), index=True)
    city: Mapped[str | None] = mapped_column(Text, index=True)
    seniority: Mapped[str] = mapped_column(String(100), index=True)
    employment_type: Mapped[str | None] = mapped_column(String(50))
    workplace_type: Mapped[str] = mapped_column(String(50), index=True)
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(20))
    salary_period: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    cleaned_description: Mapped[str] = mapped_column(Text)
    skills: Mapped[list] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(Text)
    published_date: Mapped[str | None] = mapped_column(String(10), index=True)
    collected_date: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class JobSkill(Base):
    __tablename__ = "job_skills"
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    skill: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)


class JobChunk(Base):
    __tablename__ = "job_chunks"
    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(
        Vector(get_settings().embedding_dimensions).with_variant(JSON(), "sqlite")
    )
    embedding_space: Mapped[str] = mapped_column(String(100), index=True)
    job_title: Mapped[str] = mapped_column(Text)
    seniority: Mapped[str] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(Text)
    company: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (Index("ix_chunks_job_sequence", "job_id", "chunk_index", unique=True),)


class JobChunkV2(Base):
    """Side-by-side 384-dimensional neural index; V1 remains available for rollback."""

    __tablename__ = "job_chunks_v2"
    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(Vector(384).with_variant(JSON(), "sqlite"))
    embedding_space: Mapped[str] = mapped_column(String(100), index=True)
    job_title: Mapped[str] = mapped_column(Text)
    seniority: Mapped[str] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(Text)
    company: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (Index("ix_chunks_v2_job_sequence", "job_id", "chunk_index", unique=True),)


class IndexState(Base):
    __tablename__ = "index_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    details: Mapped[dict] = mapped_column(JSON)
