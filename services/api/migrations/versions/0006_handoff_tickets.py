"""Add consented human-handoff tickets.

Revision ID: 0006_handoff_tickets
Revises: 0005_admin_account_recovery
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_handoff_tickets"
down_revision = "0005_admin_account_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "handoff_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("contact", sa.String(255)),
        sa.Column("contact_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("internal_note", sa.Text()),
        sa.Column("resolved_by_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("admin_users.id")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_handoff_tickets_conversation_id", "handoff_tickets", ["conversation_id"])
    op.create_index("ix_handoff_tickets_status", "handoff_tickets", ["status"])
    op.create_index("ix_handoff_tickets_resolved_by_id", "handoff_tickets", ["resolved_by_id"])


def downgrade() -> None:
    op.drop_table("handoff_tickets")
