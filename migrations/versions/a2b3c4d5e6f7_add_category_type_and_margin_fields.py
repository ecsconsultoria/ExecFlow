"""add category_type to vehicle_categories and margin fields to orders

Revision ID: a2b3c4d5e6f7
Revises: f8a9c1e2d3b4
Create Date: 2026-05-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a2b3c4d5e6f7'
down_revision = 'f8a9c1e2d3b4'
branch_labels = None
depends_on = None


def _col_exists(table, column):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def upgrade():
    # ── vehicle_categories: add category_type ────────────────────────────────
    if not _col_exists('vehicle_categories', 'category_type'):
        with op.batch_alter_table('vehicle_categories') as batch_op:
            batch_op.add_column(sa.Column('category_type', sa.String(50),
                                          nullable=False, server_default='transport'))
        # backfill
        op.execute("UPDATE vehicle_categories SET category_type = 'transport' WHERE category_type IS NULL")

    # ── orders: add total_po_cost and margin_amount ───────────────────────────
    for col_name in ('total_po_cost', 'margin_amount'):
        if not _col_exists('orders', col_name):
            with op.batch_alter_table('orders') as batch_op:
                batch_op.add_column(sa.Column(col_name, sa.Float(), nullable=True,
                                              server_default='0'))

    # ── Seed expense categories ───────────────────────────────────────────────
    conn = op.get_bind()
    expense_categories = [
        ('Combustível',                  'combustivel',               'expense'),
        ('Hotel',                        'hotel',                     'expense'),
        ('Alimentação',                  'alimentacao',               'expense'),
        ('Pedágio',                      'pedagio',                   'expense'),
        ('Estacionamento',               'estacionamento',            'expense'),
        ('Impostos',                     'impostos',                  'expense'),
        ('Taxas Aeroportuárias',         'taxas-aeroportuarias',      'expense'),
        ('Manutenção',                   'manutencao',                'expense'),
        ('Custo do Motorista',           'custo-motorista',           'expense'),
        ('Transporte Terceirizado',      'transporte-terceirizado',   'expense'),
        ('Despesa Operacional Diversa',  'despesa-diversa',           'expense'),
        ('Financiamento',                'financiamento',             'financial_expense'),
    ]
    for name, slug, cat_type in expense_categories:
        existing = conn.execute(
            sa.text("SELECT id FROM vehicle_categories WHERE name = :name"),
            {'name': name}
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text("""
                    INSERT INTO vehicle_categories
                        (name, slug, category_type, is_active, sort_order, km_extra_rate,
                         created_at, updated_at)
                    VALUES
                        (:name, :slug, :cat_type, 1, 99, 0,
                         datetime('now'), datetime('now'))
                """),
                {'name': name, 'slug': slug, 'cat_type': cat_type}
            )
        else:
            conn.execute(
                sa.text("UPDATE vehicle_categories SET category_type = :ct WHERE name = :name"),
                {'ct': cat_type, 'name': name}
            )


def downgrade():
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_column('margin_amount')
        batch_op.drop_column('total_po_cost')

    with op.batch_alter_table('vehicle_categories') as batch_op:
        batch_op.drop_column('category_type')
