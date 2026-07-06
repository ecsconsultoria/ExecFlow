"""add usd_rate to quotes and orders

Revision ID: e7f8a9b0c1d2
Revises: d1e2f3a4b5c6
Create Date: 2026-07-06 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e7f8a9b0c1d2'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def _col_exists(table, column):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def upgrade():
    for table in ('quotes', 'orders'):
        if not _col_exists(table, 'usd_rate'):
            with op.batch_alter_table(table) as batch_op:
                batch_op.add_column(sa.Column('usd_rate', sa.Float(), nullable=True))


def downgrade():
    for table in ('quotes', 'orders'):
        if _col_exists(table, 'usd_rate'):
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column('usd_rate')
