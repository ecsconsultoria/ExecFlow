"""add expense link columns to financial_records (Etapa 3B)

Revision ID: c4d2e9f0a1b5
Revises: a3c1f8d2e6b4
Create Date: 2026-08-28 00:00:00.000000

UP:
  * financial_records ganha supplier_id / order_id / purchase_order_id
    (nullable, FK) para o módulo de Despesas Gerais — a despesa usa o
    PRÓPRIO FinancialRecord como ledger (type='expense'), sem tabela nova.
  * NENHUM registro histórico é alterado (colunas ficam NULL).

DOWN:
  * Remove as três colunas novas. Nada destrutivo em tabelas pré-existentes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d2e9f0a1b5'
down_revision = 'a3c1f8d2e6b4'
branch_labels = None
depends_on = None

_NEW_COLS = {
    "supplier_id":       {"fk_table": "suppliers",       "fk_col": "id"},
    "order_id":          {"fk_table": "orders",          "fk_col": "id"},
    "purchase_order_id": {"fk_table": "purchase_orders", "fk_col": "id"},
}


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    fr_cols = {c["name"] for c in insp.get_columns('financial_records')}

    def add_sqlite(batch_op, col):
        batch_op.add_column(sa.Column(col, sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            f"fk_financial_records_{col}", _NEW_COLS[col]["fk_table"],
            [col], [_NEW_COLS[col]["fk_col"]])

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("financial_records") as batch_op:
            for col in _NEW_COLS:
                if col not in fr_cols:
                    add_sqlite(batch_op, col)
    else:
        for col in _NEW_COLS:
            if col not in fr_cols:
                op.add_column('financial_records', sa.Column(
                    col, sa.Integer(),
                    sa.ForeignKey(f"{_NEW_COLS[col]['fk_table']}.{_NEW_COLS[col]['fk_col']}"),
                    nullable=True))


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if 'financial_records' not in insp.get_table_names():
        return
    fr_cols = {c["name"] for c in insp.get_columns('financial_records')}
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("financial_records") as batch_op:
            for col in reversed(list(_NEW_COLS)):
                if col in fr_cols:
                    batch_op.drop_column(col)
    else:
        for col in reversed(list(_NEW_COLS)):
            if col in fr_cols:
                op.drop_column('financial_records', col)
