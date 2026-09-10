"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from app.config import get_settings

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

_EMBEDDING_DIM = get_settings().embedding_dimensions


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admission_year", sa.Integer(), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_admission_year", "documents", ["admission_year"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admission_year", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.String(500), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(_EMBEDDING_DIM), nullable=True),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_admission_year", "chunks", ["admission_year"])

    op.create_table(
        "search_queries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admission_year", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("device_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_search_queries_admission_year", "search_queries", ["admission_year"])
    op.create_index("ix_search_queries_device_id", "search_queries", ["device_id"])

    op.create_table(
        "stage_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("search_query_id", sa.Integer(), sa.ForeignKey("search_queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_stage_results_search_query_id", "stage_results", ["search_query_id"])

    op.create_table(
        "highlights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admission_year", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_highlights_chunk_id", "highlights", ["chunk_id"])
    op.create_index("ix_highlights_admission_year", "highlights", ["admission_year"])
    op.create_index("ix_highlights_document_id", "highlights", ["document_id"])
    op.create_index("ix_highlights_device_id", "highlights", ["device_id"])

    op.create_table(
        "evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("search_query_id", sa.Integer(), sa.ForeignKey("search_queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admission_year", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("suggestion_helpful", sa.Boolean(), nullable=True),
        sa.Column("answer_resolved", sa.Boolean(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("device_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_evaluations_search_query_id", "evaluations", ["search_query_id"])
    op.create_index("ix_evaluations_admission_year", "evaluations", ["admission_year"])


def downgrade() -> None:
    op.drop_table("evaluations")
    op.drop_table("highlights")
    op.drop_table("stage_results")
    op.drop_table("search_queries")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.execute("DROP EXTENSION IF EXISTS vector")
