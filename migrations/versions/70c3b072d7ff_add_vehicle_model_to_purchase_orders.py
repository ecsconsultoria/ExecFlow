"""add_vehicle_model_to_purchase_orders

Revision ID: 70c3b072d7ff
Revises: 1872379e5cb7
Create Date: 2026-05-24 11:51:54.000201

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '70c3b072d7ff'
down_revision = '1872379e5cb7'
branch_labels = None
depends_on = None


def _col_exists(table, column):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def upgrade():
    if not _col_exists('purchase_orders', 'vehicle_model'):
        with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
            batch_op.add_column(sa.Column('vehicle_model', sa.String(length=200), nullable=True))


def downgrade():
    with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
        batch_op.drop_column('vehicle_model')

    # ### end Alembic commands ###
