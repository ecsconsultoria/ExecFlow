"""add op_service to order_items

Revision ID: a1c2d3e4f5b6
Revises: f0a1b2c3d4e5
Create Date: 2026-10-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c2d3e4f5b6'
down_revision = 'f0a1b2c3d4e5'
branch_labels = None
depends_on = None


def _column_exists(table, column):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def upgrade():
    if not _column_exists('order_items', 'op_service'):
        with op.batch_alter_table('order_items', schema=None) as batch_op:
            batch_op.add_column(sa.Column('op_service', sa.String(length=500), nullable=True))


def downgrade():
    if _column_exists('order_items', 'op_service'):
        with op.batch_alter_table('order_items', schema=None) as batch_op:
            batch_op.drop_column('op_service')
