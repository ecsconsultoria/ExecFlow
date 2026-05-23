"""add operational flag columns to services

Revision ID: a1b2c3d4e5f6
Revises: 982d9892837b
Create Date: 2026-05-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '982d9892837b'
branch_labels = None
depends_on = None

_COLS = [
    'is_operational',
    'requires_route',
    'requires_passenger',
    'requires_vehicle',
    'requires_dispatch',
    'requires_schedule',
]


def upgrade():
    # Idempotent: only add columns that don't already exist.
    conn = op.get_bind()
    insp = inspect(conn)
    existing = {c['name'] for c in insp.get_columns('services')}
    missing = [c for c in _COLS if c not in existing]
    if missing:
        with op.batch_alter_table('services', schema=None) as batch_op:
            for col in missing:
                batch_op.add_column(
                    sa.Column(col, sa.Boolean(), nullable=True, server_default=sa.false())
                )


def downgrade():
    with op.batch_alter_table('services', schema=None) as batch_op:
        for col in reversed(_COLS):
            batch_op.drop_column(col)
