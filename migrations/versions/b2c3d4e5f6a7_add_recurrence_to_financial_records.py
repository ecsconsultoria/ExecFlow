"""add recurrence columns to financial_records

Revision ID: b2c3d4e5f6a7
Revises: a1b9c8d7e6f5
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b9c8d7e6f5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("financial_records", sa.Column("recurrence", sa.String(length=20), nullable=True))
    op.add_column("financial_records", sa.Column("recurrence_until", sa.Date(), nullable=True))
    op.add_column("financial_records", sa.Column("recurrence_active",
                                                 sa.Boolean(), nullable=True,
                                                 server_default=sa.false()))
    op.add_column("financial_records", sa.Column("next_run", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("financial_records", "next_run")
    op.drop_column("financial_records", "recurrence_active")
    op.drop_column("financial_records", "recurrence_until")
    op.drop_column("financial_records", "recurrence")
