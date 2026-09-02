"""Add session revocation and ingestion job integrity.

Revision ID: 0004_session_job_integrity
Revises: 0003_search_indexes
Create Date: 2026-08-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_session_job_integrity"
down_revision = "0003_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
    )
    # The application models one durable ingestion job per document. Collapse any
    # historical duplicates deterministically before enforcing that invariant.
    op.execute(
        """
        DELETE FROM ingestion_jobs older
        USING ingestion_jobs newer
        WHERE older.document_id = newer.document_id
          AND (older.created_at, older.id) < (newer.created_at, newer.id)
        """
    )
    op.create_unique_constraint(
        "uq_ingestion_jobs_document_id",
        "ingestion_jobs",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ingestion_jobs_document_id",
        "ingestion_jobs",
        type_="unique",
    )
    op.drop_column("admin_users", "session_version")
