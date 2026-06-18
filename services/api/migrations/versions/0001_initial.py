"""Initial production schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    channel = postgresql.ENUM("website", "whatsapp", "admin", name="channel", create_type=False)
    confidence = postgresql.ENUM("verified", "high", "medium", "low", name="confidence", create_type=False)
    route = postgresql.ENUM("faq", "metric", "rag", "website", "fallback", name="retrievalroute", create_type=False)
    channel.create(op.get_bind(), checkfirst=True)
    confidence.create(op.get_bind(), checkfirst=True)
    route.create(op.get_bind(), checkfirst=True)

    op.create_table("admin_users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_admin_users_email", "admin_users", ["email"])
    op.create_table("faqs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table("metrics",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(180), nullable=False, unique=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(40)),
        sa.Column("verified_by", sa.String(180), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("is_sensitive_stat", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_metrics_name", "metrics", ["name"])
    op.create_table("documents",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("admin_users.id")),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_title", "documents", ["title"])
    op.create_table("document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("section", sa.String(255)),
        sa.Column("embedding_id", sa.String(255)),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_embedding_id", "document_chunks", ["embedding_id"])
    op.create_table("conversations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("channel", channel, nullable=False),
        sa.Column("user_ref", sa.String(255)),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_channel", "conversations", ["channel"])
    op.create_index("ix_conversations_user_ref", "conversations", ["user_ref"])
    op.create_table("conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", confidence),
        sa.Column("route", route),
        sa.Column("citations", postgresql.JSONB(), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"])
    op.create_table("feedback",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feedback_message_id", "feedback", ["message_id"])
    op.create_table("analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("channel", channel),
        sa.Column("query", sa.Text()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("route", route),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_analytics_events_event_type", "analytics_events", ["event_type"])


def downgrade() -> None:
    for table in ["analytics_events", "feedback", "conversation_messages", "conversations", "document_chunks", "documents", "metrics", "faqs", "admin_users"]:
        op.drop_table(table)
    postgresql.ENUM(name="retrievalroute").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="confidence").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="channel").drop(op.get_bind(), checkfirst=True)
