"""Add administrator identity, OTP challenges, and login protection.

Revision ID: 0007_secure_admin_otp
Revises: 0006_handoff_tickets
Create Date: 2026-09-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007_secure_admin_otp"
down_revision = "0006_handoff_tickets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_users", sa.Column("name", sa.String(180), nullable=False, server_default="CIET Administrator"))
    op.add_column("admin_users", sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.add_column("admin_users", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("admin_users", sa.Column("locked_until", sa.DateTime(timezone=True)))
    op.add_column("admin_users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table(
        "admin_otp_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("admin_user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("challenge_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("resend_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_admin_otp_challenges_admin_user_id", "admin_otp_challenges", ["admin_user_id"])
    op.create_index("ix_admin_otp_challenges_challenge_hash", "admin_otp_challenges", ["challenge_hash"])
    op.create_index("ix_admin_otp_challenges_expires_at", "admin_otp_challenges", ["expires_at"])


def downgrade() -> None:
    op.drop_table("admin_otp_challenges")
    op.drop_column("admin_users", "mfa_enabled")
    op.drop_column("admin_users", "locked_until")
    op.drop_column("admin_users", "failed_login_count")
    op.drop_column("admin_users", "last_login_at")
    op.drop_column("admin_users", "name")
