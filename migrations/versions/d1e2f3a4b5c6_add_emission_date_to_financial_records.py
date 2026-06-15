"""add_emission_date_to_financial_records

Revision ID: d1e2f3a4b5c6
Revises: f8a9c1e2d3b4
Create Date: 2026-06-02 00:00:00.000000

Adds emission_date (data de emissão / data contábil) to financial_records.
Used as the accounting reference date for period filtering in the financial panel and dashboard.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd1e2f3a4b5c6'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def _col_exists(table, column):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def upgrade():
    if not _col_exists('financial_records', 'emission_date'):
        with op.batch_alter_table('financial_records', schema=None) as batch_op:
            batch_op.add_column(sa.Column('emission_date', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('financial_records', schema=None) as batch_op:
        batch_op.drop_column('emission_date')
