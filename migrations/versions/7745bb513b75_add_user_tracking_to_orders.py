"""add user tracking to orders

Revision ID: 7745bb513b75
Revises: 5ea291e3c3ce
Create Date: 2026-05-24 10:33:22.479102

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7745bb513b75'
down_revision = '5ea291e3c3ce'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('opened_by',    sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('invoiced_by',  sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('closed_by',    sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('cancelled_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('reopened_by',  sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('reopened_by')
        batch_op.drop_column('cancelled_by')
        batch_op.drop_column('closed_by')
        batch_op.drop_column('invoiced_by')
        batch_op.drop_column('opened_by')
