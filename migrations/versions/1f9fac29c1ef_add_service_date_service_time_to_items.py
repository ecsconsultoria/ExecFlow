"""add service_date service_time to items

Revision ID: 1f9fac29c1ef
Revises: e7f8a9b0c1d2
Create Date: 2026-07-29 21:00:54.392482

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1f9fac29c1ef'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('quote_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('service_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('service_time', sa.Time(), nullable=True))

    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('service_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('service_time', sa.Time(), nullable=True))

    with op.batch_alter_table('po_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('service_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('service_time', sa.Time(), nullable=True))


def downgrade():
    with op.batch_alter_table('po_items', schema=None) as batch_op:
        batch_op.drop_column('service_time')
        batch_op.drop_column('service_date')

    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.drop_column('service_time')
        batch_op.drop_column('service_date')

    with op.batch_alter_table('quote_items', schema=None) as batch_op:
        batch_op.drop_column('service_time')
        batch_op.drop_column('service_date')
