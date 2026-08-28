"""add financial_categories and cost_centers (Etapa 3A)

Revision ID: a3c1f8d2e6b4
Revises: b5c6d7e8f9a0
Create Date: 2026-08-28 00:00:00.000000

UP:
  * Cria `financial_categories` (hierárquica, por company) e `cost_centers`.
  * Adiciona `financial_records.financial_category_id` / `cost_center_id`
    (nullable — NENHUM registro histórico é alterado; valores ficam NULL).
    SQLite usa batch mode (copy-and-move) por causa da restrição FK;
    PostgreSQL usa ADD COLUMN comum.
  * Índice parcial UNIQUE em `financial_records.reference` somente para
    registros ATIVOS (deleted_at IS NULL) e com reference preenchida —
    protege contra duplicidade lógica sem impedir o ciclo void → re-baixa.
    (Análise prévia: 0 duplicidades ativas na base.)

DOWN:
  * Remove o índice parcial, as duas colunas e as duas tabelas novas.
  * Nada destrutivo em tabelas/colunas pré-existentes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3c1f8d2e6b4'
down_revision = 'b5c6d7e8f9a0'
branch_labels = None
depends_on = None

_UNIQUE_INDEX = "uq_financial_records_active_reference"


def _index_exists(conn, name):
    insp = sa.inspect(conn)
    if 'financial_records' in insp.get_table_names():
        return name in [i["name"] for i in insp.get_indexes('financial_records')]
    return False


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())

    # 1. Tabela de categorias financeiras (hierárquica)
    if 'financial_categories' not in tables:
        op.create_table(
            'financial_categories',
            sa.Column('id',          sa.Integer(),    nullable=False),
            sa.Column('company_id',  sa.Integer(),    nullable=False),
            sa.Column('name',        sa.String(100),  nullable=False),
            sa.Column('description', sa.String(255),  nullable=True),
            sa.Column('type',        sa.String(20),   nullable=False),
            sa.Column('parent_id',   sa.Integer(),    nullable=True),
            sa.Column('active',      sa.Boolean(),    nullable=False),
            sa.Column('created_at',  sa.DateTime(),   nullable=False),
            sa.Column('updated_at',  sa.DateTime(),   nullable=False),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
            sa.ForeignKeyConstraint(['parent_id'],  ['financial_categories.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_financial_categories_company_id', 'financial_categories', ['company_id'])

    # 2. Tabela de centros de custo
    if 'cost_centers' not in tables:
        op.create_table(
            'cost_centers',
            sa.Column('id',          sa.Integer(),    nullable=False),
            sa.Column('company_id',  sa.Integer(),    nullable=False),
            sa.Column('name',        sa.String(100),  nullable=False),
            sa.Column('description', sa.String(255),  nullable=True),
            sa.Column('active',      sa.Boolean(),    nullable=False),
            sa.Column('created_at',  sa.DateTime(),   nullable=False),
            sa.Column('updated_at',  sa.DateTime(),   nullable=False),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_cost_centers_company_id', 'cost_centers', ['company_id'])

    # 3. Colunas opcionais em financial_records (nenhum dado histórico tocado)
    fr_cols = {c["name"] for c in insp.get_columns('financial_records')}
    if conn.dialect.name == "sqlite":
        # SQLite não suporta ADD COLUMN com FK — usa batch (copy-and-move)
        with op.batch_alter_table("financial_records") as batch_op:
            if 'financial_category_id' not in fr_cols:
                batch_op.add_column(sa.Column('financial_category_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_financial_records_financial_category_id',
                    'financial_categories', ['financial_category_id'], ['id'])
            if 'cost_center_id' not in fr_cols:
                batch_op.add_column(sa.Column('cost_center_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_financial_records_cost_center_id',
                    'cost_centers', ['cost_center_id'], ['id'])
    else:
        if 'financial_category_id' not in fr_cols:
            op.add_column('financial_records', sa.Column(
                'financial_category_id', sa.Integer(),
                sa.ForeignKey('financial_categories.id'), nullable=True))
        if 'cost_center_id' not in fr_cols:
            op.add_column('financial_records', sa.Column(
                'cost_center_id', sa.Integer(),
                sa.ForeignKey('cost_centers.id'), nullable=True))

    # 4. Índice parcial UNIQUE (registros ativos com reference preenchida)
    if not _index_exists(conn, _UNIQUE_INDEX):
        op.execute(
            f"CREATE UNIQUE INDEX {_UNIQUE_INDEX} ON financial_records (reference) "
            "WHERE deleted_at IS NULL AND reference IS NOT NULL"
        )


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # 1. Índice parcial
    if _index_exists(conn, _UNIQUE_INDEX):
        op.execute(f"DROP INDEX {_UNIQUE_INDEX}")

    # 2. Colunas novas (se existirem)
    if 'financial_records' in insp.get_table_names():
        fr_cols = {c["name"] for c in insp.get_columns('financial_records')}
        if conn.dialect.name == "sqlite":
            with op.batch_alter_table("financial_records") as batch_op:
                if 'cost_center_id' in fr_cols:
                    batch_op.drop_column('cost_center_id')
                if 'financial_category_id' in fr_cols:
                    batch_op.drop_column('financial_category_id')
        else:
            if 'cost_center_id' in fr_cols:
                op.drop_column('financial_records', 'cost_center_id')
            if 'financial_category_id' in fr_cols:
                op.drop_column('financial_records', 'financial_category_id')

    # 3. Tabelas novas
    tables = set(insp.get_table_names())
    if 'cost_centers' in tables:
        op.drop_table('cost_centers')
    if 'financial_categories' in tables:
        op.drop_table('financial_categories')
