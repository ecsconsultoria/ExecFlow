"""add payment_receipts

Revision ID: b5c6d7e8f9a0
Revises: 1f9fac29c1ef
Create Date: 2026-08-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5c6d7e8f9a0'
down_revision = '1f9fac29c1ef'
branch_labels = None
depends_on = None


def upgrade():
    # Guard de existência: db.create_all() já cria a tabela em dev antes do upgrade.
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if 'payment_receipts' in insp.get_table_names():
        return
    op.create_table(
        'payment_receipts',
        sa.Column('id',             sa.Integer(),    nullable=False),
        sa.Column('company_id',     sa.Integer(),    nullable=False),
        sa.Column('order_id',       sa.Integer(),    nullable=False),
        sa.Column('payment_id',     sa.Integer(),    nullable=False),
        sa.Column('receipt_number', sa.String(50),   nullable=False),
        sa.Column('issued_at',      sa.DateTime(),   nullable=False),
        sa.Column('issued_by',      sa.Integer(),    nullable=True),
        sa.Column('created_at',     sa.DateTime(),   nullable=False),
        sa.Column('updated_at',     sa.DateTime(),   nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['order_id'],   ['orders.id']),
        sa.ForeignKeyConstraint(['payment_id'], ['order_payments.id']),
        sa.ForeignKeyConstraint(['issued_by'],  ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_id'),
        sa.UniqueConstraint('receipt_number'),
    )


def downgrade():
    op.drop_table('payment_receipts')
