"""limpa op_driver_name de po_items preenchido com o TIPO do motorista (Monolíngue/Bilíngue)

Revision ID: c9d1e2f3a4b5
Revises: a1c2d3e4f5b6
Create Date: 2026-11-13

Antes do fix em purchase_order_service, a criação de PO a partir de SO gravava
item.driver_name (tipo Monolíngue/Bilíngue) em op_driver_name. Esta migração:
  1. cria a tabela de backup po_items_driver_cleanup_backup (se não existir);
  2. recupera o nome real do item espelhado da SO de origem (order_id +
     sort_order, mesmo serviço) quando houver;
  3. zera op_driver_name nos itens sem espelho com nome real.

Idempotente: uma segunda execução não encontra linhas poluídas e não faz nada.
downgrade restaura os valores antigos a partir do backup.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9d1e2f3a4b5'
down_revision = 'a1c2d3e4f5b6'
branch_labels = None
depends_on = None

POLLUTED = ("Monolíngue", "Bilíngue")
BACKUP_TABLE = "po_items_driver_cleanup_backup"


def _fetch_mirrored(bind, order_id, sort_order, service_id):
    """Busca o item espelhado da SO de origem; devolve (so_item_id, nome) ou (None, None)."""
    row = bind.execute(sa.text(
        """
        SELECT id, service_id, op_driver_name
          FROM order_items
         WHERE order_id = :oid AND sort_order = :so
         ORDER BY id
         LIMIT 1
        """
    ), {"oid": order_id, "so": sort_order or 0}).fetchone()
    if row is None:
        return None, None
    oi_id, oi_service_id, oi_name = row[0], row[1], row[2]
    # se ambos têm serviço e divergem, o espelhamento não vale para este item
    if service_id and oi_service_id and int(service_id) != int(oi_service_id):
        return None, None
    if oi_name and str(oi_name).strip() and str(oi_name).strip() not in POLLUTED:
        return oi_id, oi_name
    return None, None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if BACKUP_TABLE not in insp.get_table_names():
        op.create_table(
            BACKUP_TABLE,
            sa.Column("po_item_id", sa.Integer, primary_key=True),
            sa.Column("po_id", sa.Integer, nullable=True),
            sa.Column("old_op_driver_name", sa.String(200), nullable=True),
            sa.Column("recovered_from_so_item_id", sa.Integer, nullable=True),
            sa.Column("cleaned_at", sa.DateTime, server_default=sa.func.now()),
        )

    rows = bind.execute(sa.text(
        """
        SELECT pi.id, pi.po_id, pi.sort_order, pi.service_id, po.order_id
          FROM po_items pi
          JOIN purchase_orders po ON po.id = pi.po_id
         WHERE pi.op_driver_name IN (:a, :b)
        """
    ), {"a": POLLUTED[0], "b": POLLUTED[1]}).fetchall()

    cleaned = 0
    for pi_id, pi_po_id, sort_order, service_id, order_id in rows:
        recovered_from = None
        recovered_name = None
        if order_id is not None:
            recovered_from, recovered_name = _fetch_mirrored(bind, order_id, sort_order, service_id)

        old = bind.execute(
            sa.text("SELECT op_driver_name FROM po_items WHERE id = :i"), {"i": pi_id}
        ).scalar()

        # Backup de cautela (só insere se ainda não houver registro)
        exists = bind.execute(
            sa.text(f"SELECT 1 FROM {BACKUP_TABLE} WHERE po_item_id = :i"), {"i": pi_id}
        ).scalar()
        if not exists:
            bind.execute(
                sa.text(
                    f"""
                    INSERT INTO {BACKUP_TABLE}
                        (po_item_id, po_id, old_op_driver_name, recovered_from_so_item_id)
                    VALUES (:pi, :po, :old, :rf)
                    """
                ),
                {"pi": pi_id, "po": pi_po_id, "old": old, "rf": recovered_from},
            )

        bind.execute(
            sa.text("UPDATE po_items SET op_driver_name = :v WHERE id = :i"),
            {"v": recovered_name, "i": pi_id},
        )
        cleaned += 1

    print(f"[clean_po_items_driver_type] {cleaned} item(ns) de PO corrigido(s)")


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if BACKUP_TABLE not in insp.get_table_names():
        return
    for pid, old in bind.execute(
        sa.text(f"SELECT po_item_id, old_op_driver_name FROM {BACKUP_TABLE}")
    ).fetchall():
        if old is not None:
            bind.execute(
                sa.text("UPDATE po_items SET op_driver_name = :v WHERE id = :i"),
                {"v": old, "i": pid},
            )
