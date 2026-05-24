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


def _col_exists(table, column):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def upgrade():
    cols = ['opened_by', 'invoiced_by', 'closed_by', 'cancelled_by', 'reopened_by']
    missing = [c for c in cols if not _col_exists('orders', c)]
    if missing:
        with op.batch_alter_table('orders', schema=None) as batch_op:
            for name in missing:
                batch_op.add_column(sa.Column(name, sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('reopened_by')
        batch_op.drop_column('cancelled_by')
        batch_op.drop_column('closed_by')
        batch_op.drop_column('invoiced_by')
        batch_op.drop_column('opened_by')
