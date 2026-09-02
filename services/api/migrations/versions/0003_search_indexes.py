"""Add bounded-search indexes for FAQ, metric, and document retrieval.

Revision ID: 0003_search_indexes
Revises: 0002_hardening
Create Date: 2026-07-21
"""

from alembic import op


revision = "0003_search_indexes"
down_revision = "0002_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX IF NOT EXISTS ix_faqs_question_trgm ON faqs USING gin (question gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_metrics_name_trgm ON metrics USING gin (name gin_trgm_ops)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_content_trgm "
        "ON document_chunks USING gin (content gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_trgm")
    op.execute("DROP INDEX IF EXISTS ix_metrics_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_faqs_question_trgm")
