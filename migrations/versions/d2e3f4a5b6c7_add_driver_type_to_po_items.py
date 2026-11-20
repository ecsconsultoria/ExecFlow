"""add driver_type to po_items + backfill a partir do item espelhado da SO

Revision ID: d2e3f4a5b6c7
Revises: c9d1e2f3a4b5
Create Date: 2026-11-20

O POItem nao tinha coluna para o TIPO do motorista (Monolíngue/Bilíngue) —
a coluna "Motorista" da tabela do PO exibia op_driver_name (nome). Esta
migracao cria driver_type e preenche os itens de POs vindos de SO com o
tipo do item espelhado da SO de origem. Itens de abertura avulsa historicos
ficam NULL (sem origem conhecida).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2e3f4a5b6c7'
down_revision = 'c9d1e2f3a4b5'
branch_labels = None
depends_on = None


def _column_exists(table, column):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in [c['name'] for c in insp.get_columns(table)]


def upgrade():
    if not _column_exists('po_items', 'driver_type'):
        with op.batch_alter_table('po_items', schema=None) as batch_op:
            batch_op.add_column(sa.Column('driver_type', sa.String(length=50), nullable=True))

    bind = op.get_bind()

    # Backfill: para cada PO vinda de SO, alinha os itens por posicao relativa
    # (sort_order, id) — cobre o off-by-one de SOs legadas com sort 1-based.
    po_rows = bind.execute(sa.text(
        """
        SELECT id, order_id FROM purchase_orders
         WHERE order_id IS NOT NULL
        """
    )).fetchall()

    filled = 0
    for po_id, order_id in po_rows:
        ois = bind.execute(sa.text(
            """
            SELECT service_id, driver_name FROM order_items
             WHERE order_id = :o
             ORDER BY COALESCE(sort_order, 0), id
            """
        ), {"o": order_id}).fetchall()
        if not ois:
            continue
        pis = bind.execute(sa.text(
            """
            SELECT id, service_id FROM po_items
             WHERE po_id = :p AND driver_type IS NULL
             ORDER BY COALESCE(sort_order, 0), id
            """
        ), {"p": po_id}).fetchall()
        for (pi_id, pi_svc), (oi_svc, oi_type) in zip(pis, ois):
            if not oi_type:
                continue
            # so preenche quando os servicos batem (ou algum deles e nulo)
            if pi_svc and oi_svc and int(pi_svc) != int(oi_svc):
                continue
            bind.execute(
                sa.text("UPDATE po_items SET driver_type = :v WHERE id = :i"),
                {"v": oi_type, "i": pi_id},
            )
            filled += 1
    print(f"[add_driver_type_to_po_items] {filled} item(ns) de PO com tipo preenchido da SO")


def downgrade():
    if _column_exists('po_items', 'driver_type'):
        with op.batch_alter_table('po_items', schema=None) as batch_op:
            batch_op.drop_column('driver_type')
