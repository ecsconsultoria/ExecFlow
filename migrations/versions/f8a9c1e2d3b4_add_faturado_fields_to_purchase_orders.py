"""add_faturado_fields_to_purchase_orders

Revision ID: f8a9c1e2d3b4
Revises: 70c3b072d7ff
Create Date: 2026-05-24 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8a9c1e2d3b4'
down_revision = 'b37af0b56672'
branch_labels = None
depends_on = None


def _col_exists(table, column):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def upgrade():
    cols = [
        ('invoiced_at', sa.Column('invoiced_at', sa.DateTime(), nullable=True)),
        ('invoiced_by', sa.Column('invoiced_by', sa.Integer(), nullable=True)),
    ]
    missing = [(n, c) for n, c in cols if not _col_exists('purchase_orders', n)]
    if missing:
        with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
            for _, col in missing:
                batch_op.add_column(col)


def downgrade():
    with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
        batch_op.drop_column('invoiced_by')
        batch_op.drop_column('invoiced_at')
