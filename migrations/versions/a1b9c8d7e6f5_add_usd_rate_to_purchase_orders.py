"""add usd_rate to purchase_orders

Revision ID: a1b9c8d7e6f5
Revises: c4d2e9f0a1b5
Create Date: 2026-09-11 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b9c8d7e6f5'
down_revision = 'c4d2e9f0a1b5'
branch_labels = None
depends_on = None


def _col_exists(table, column):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def upgrade():
    if not _col_exists('purchase_orders', 'usd_rate'):
        with op.batch_alter_table('purchase_orders') as batch_op:
            batch_op.add_column(sa.Column('usd_rate', sa.Float(), nullable=True))


def downgrade():
    if _col_exists('purchase_orders', 'usd_rate'):
        with op.batch_alter_table('purchase_orders') as batch_op:
            batch_op.drop_column('usd_rate')
