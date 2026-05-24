"""add discount fields to purchase_orders

Revision ID: 1872379e5cb7
Revises: 7745bb513b75
Create Date: 2026-05-24 10:57:59.432866

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1872379e5cb7'
down_revision = '7745bb513b75'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('discount_type', sa.String(length=5), nullable=True))
        batch_op.add_column(sa.Column('discount_value', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('freight_amount', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('other_costs_amount', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('other_costs_label', sa.String(length=200), nullable=True))


def downgrade():
    with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
        batch_op.drop_column('other_costs_label')
        batch_op.drop_column('other_costs_amount')
        batch_op.drop_column('freight_amount')
        batch_op.drop_column('discount_value')
        batch_op.drop_column('discount_type')
