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


def _col_exists(table, column):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def upgrade():
    cols = [('approved_by', sa.Integer()), ('rejected_by', sa.Integer())]
    missing = [(n, t) for n, t in cols if not _col_exists('quotes', n)]
    if missing:
        with op.batch_alter_table('quotes', schema=None) as batch_op:
            for name, typ in missing:
                batch_op.add_column(sa.Column(name, typ, nullable=True))


def downgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_column('rejected_by')
        batch_op.drop_column('approved_by')
