"""add approved_by and rejected_by to quotes

Revision ID: 5ea291e3c3ce
Revises: a1b2c3d4e5f6
Create Date: 2026-05-24 09:55:24.522908

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5ea291e3c3ce'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('approved_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('rejected_by', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_column('rejected_by')
        batch_op.drop_column('approved_by')
