"""add payment_terms to order_payments

Revision ID: f0a1b2c3d4e5
Revises: e8f9a0b1c2d3
Create Date: 2026-10-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f0a1b2c3d4e5'
down_revision = 'e8f9a0b1c2d3'
branch_labels = None
depends_on = None


def _column_exists(table, column):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def upgrade():
    if not _column_exists('order_payments', 'payment_terms'):
        with op.batch_alter_table('order_payments', schema=None) as batch_op:
            batch_op.add_column(sa.Column('payment_terms', sa.String(length=100), nullable=True))


def downgrade():
    if _column_exists('order_payments', 'payment_terms'):
        with op.batch_alter_table('order_payments', schema=None) as batch_op:
            batch_op.drop_column('payment_terms')
