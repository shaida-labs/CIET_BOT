"""Production hardening tables and document metadata.

Revision ID: 0002_hardening
Revises: 0001_initial
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_hardening"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("checksum", sa.String(64), nullable=True))
    op.add_column("documents", sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.create_index("ix_documents_checksum", "documents", ["checksum"], unique=True)
    op.add_column("document_chunks", sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"])

    op.create_table(
        "allowed_domains",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("domain", sa.String(255), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_allowed_domains_domain", "allowed_domains", ["domain"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("admin_users.id")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(120)),
        sa.Column("ip_address", sa.String(80)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])

    op.create_table(
        "whatsapp_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column("recipient", sa.String(80), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_message_id", name="uq_whatsapp_provider_message_id"),
    )
    op.create_index("ix_whatsapp_deliveries_provider_message_id", "whatsapp_deliveries", ["provider_message_id"])
    op.create_index("ix_whatsapp_deliveries_recipient", "whatsapp_deliveries", ["recipient"])


def downgrade() -> None:
    op.drop_table("whatsapp_deliveries")
    op.drop_table("audit_logs")
    op.drop_table("allowed_domains")
    op.drop_table("ingestion_jobs")
    op.drop_column("document_chunks", "token_count")
    op.drop_index("ix_documents_checksum", table_name="documents")
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "size_bytes")
    op.drop_column("documents", "checksum")
