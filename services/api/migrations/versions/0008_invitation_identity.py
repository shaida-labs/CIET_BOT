"""Store the invited administrator name.

Revision ID: 0008_invitation_identity
Revises: 0007_secure_admin_otp
Create Date: 2026-09-20
"""
from alembic import op
import sqlalchemy as sa


revision = "0008_invitation_identity"
down_revision = "0007_secure_admin_otp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_invitations",
        sa.Column("name", sa.String(180), nullable=False, server_default="CIET Administrator"),
    )


def downgrade() -> None:
    op.drop_column("admin_invitations", "name")
