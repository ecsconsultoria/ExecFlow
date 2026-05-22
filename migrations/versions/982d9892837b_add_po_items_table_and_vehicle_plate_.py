"""add po_items table and vehicle_plate driver_phone to po

Revision ID: 982d9892837b
Revises: c3372d487743
Create Date: 2026-05-21 01:35:26.790387

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '982d9892837b'
down_revision = 'c3372d487743'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'po_items',
        sa.Column('id',                  sa.Integer(),     nullable=False),
        sa.Column('po_id',               sa.Integer(),     nullable=False),
        sa.Column('service_id',          sa.Integer(),     nullable=True),
        sa.Column('category_id',         sa.Integer(),     nullable=True),
        sa.Column('description',         sa.String(500),   nullable=True),
        sa.Column('vehicle_description', sa.String(200),   nullable=True),
        sa.Column('quantity',            sa.Integer(),     nullable=True),
        sa.Column('unit_cost',           sa.Float(),       nullable=True),
        sa.Column('total_cost',          sa.Float(),       nullable=True),
        sa.Column('sort_order',          sa.Integer(),     nullable=True),
        sa.Column('created_at',          sa.DateTime(),    nullable=True),
        sa.Column('updated_at',          sa.DateTime(),    nullable=True),
        sa.ForeignKeyConstraint(['po_id'],       ['purchase_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'],  ['services.id']),
        sa.ForeignKeyConstraint(['category_id'], ['vehicle_categories.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vehicle_plate', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('driver_phone',  sa.String(50), nullable=True))


def downgrade():
    op.drop_table('po_items')
    with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
        batch_op.drop_column('driver_phone')
        batch_op.drop_column('vehicle_plate')
