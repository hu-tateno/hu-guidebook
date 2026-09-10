from __future__ import annotations

import datetime as dt

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db.base import Base

_EMBEDDING_DIM = get_settings().embedding_dimensions


class Document(Base):
    """One ingested handbook PDF. admission_year is the source of truth for year scoping."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admission_year: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ingested_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """A retrievable unit of text. admission_year/document_id are denormalized onto every
    row so that no query can accidentally search across admission years or documents."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBEDDING_DIM), nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks")


class SearchQuery(Base):
    """One search request. Always scoped to a single admission year."""

    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admission_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stage_results: Mapped[list["StageResult"]] = relationship(back_populates="search_query", cascade="all, delete-orphan")
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="search_query", cascade="all, delete-orphan")


class StageResult(Base):
    """Per-stage trace of one search_query, used by the admin search-trace view."""

    __tablename__ = "stage_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_query_id: Mapped[int] = mapped_column(ForeignKey("search_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    search_query: Mapped[SearchQuery] = relationship(back_populates="stage_results")


class Highlight(Base):
    """A student's PDF highlight. device_id must never be surfaced by any read endpoint."""

    __tablename__ = "highlights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Evaluation(Base):
    """Student feedback on a search_query: were the suggestions useful, was the AI answer
    resolved. device_id is stored for future de-duplication only and must never be exposed
    via CSV export or any admin API response."""

    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_query_id: Mapped[int] = mapped_column(ForeignKey("search_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suggestion_helpful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    answer_resolved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    search_query: Mapped[SearchQuery] = relationship(back_populates="evaluations")
