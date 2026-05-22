"""add po_payments and payment_terms

Revision ID: c3372d487743
Revises: 
Create Date: 2026-05-21 00:05:51.697806

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3372d487743'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('payment_terms', sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table('purchase_orders', schema=None) as batch_op:
        batch_op.drop_column('payment_terms')
