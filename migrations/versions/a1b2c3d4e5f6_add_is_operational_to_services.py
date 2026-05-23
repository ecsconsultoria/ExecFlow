"""add is_operational to services

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


def upgrade():
    # Use inspect() so this migration is idempotent — safe to run even if the
    # column was already added manually (e.g. via _ensure_schema_columns).
    conn = op.get_bind()
    insp = inspect(conn)
    existing = {c['name'] for c in insp.get_columns('services')}
    if 'is_operational' not in existing:
        with op.batch_alter_table('services', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('is_operational', sa.Boolean(),
                          nullable=True, server_default=sa.false())
            )


def downgrade():
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.drop_column('is_operational')
