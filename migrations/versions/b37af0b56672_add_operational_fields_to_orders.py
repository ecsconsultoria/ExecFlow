"""add_operational_fields_to_orders

Revision ID: b37af0b56672
Revises: 70c3b072d7ff
Create Date: 2026-05-24 12:10:10.827516

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b37af0b56672'
down_revision = '70c3b072d7ff'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('driver_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('driver_phone', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('vehicle_model', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('vehicle_plate', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('pickup_location', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('dropoff_location', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('passenger_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('passenger_phone', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('flight_number', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('pax_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('vehicle_description', sa.String(length=200), nullable=True))


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('vehicle_description')
        batch_op.drop_column('pax_count')
        batch_op.drop_column('flight_number')
        batch_op.drop_column('passenger_phone')
        batch_op.drop_column('passenger_name')
        batch_op.drop_column('dropoff_location')
        batch_op.drop_column('pickup_location')
        batch_op.drop_column('vehicle_plate')
        batch_op.drop_column('vehicle_model')
        batch_op.drop_column('driver_phone')
        batch_op.drop_column('driver_name')
        batch_op.drop_column('pax_count')
        batch_op.drop_column('flight_number')
        batch_op.drop_column('passenger_phone')
        batch_op.drop_column('passenger_name')
        batch_op.drop_column('dropoff_location')
        batch_op.drop_column('pickup_location')
        batch_op.drop_column('vehicle_plate')
        batch_op.drop_column('vehicle_model')
        batch_op.drop_column('driver_phone')
        batch_op.drop_column('driver_name')

    # ### end Alembic commands ###
