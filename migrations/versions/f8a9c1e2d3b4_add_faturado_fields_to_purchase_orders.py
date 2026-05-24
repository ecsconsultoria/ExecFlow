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


def upgrade():
    with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('invoiced_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('invoiced_by', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
        batch_op.drop_column('invoiced_by')
        batch_op.drop_column('invoiced_at')
