"""cancela lancamentos financeiros orfaos de parcelas removidas (PO/SO)

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-11-23

Soft-deleta FinancialRecords PENDENTES cuja referencia (po_payment:/order_payment:)
aponta para uma parcela que nao existe mais. Esses orfaos ficavam "Pendente"
para sempre no extrato de Contas a Pagar (ex.: FR da PO-260728-001 de R$ 4.000
apos regeneracao com desconto).

Cautela:
- So registros NAO pagos (status pendente/vencido) sao cancelados — pagos
  sao historico financeiro e nunca sao tocados.
- Backup completo em fr_orphan_cleanup_backup antes de cada UPDATE.
- Idempotente: segunda execucao nao encontra orfaos e nao faz nada.
- downgrade restaura deleted_at=NULL dos registros do backup.
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3f4a5b6c7d8'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None

BACKUP_TABLE = "fr_orphan_cleanup_backup"
_TABLE_BY_PREFIX = {"po_payment": "po_payments", "order_payment": "order_payments"}


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if BACKUP_TABLE not in insp.get_table_names():
        op.create_table(
            BACKUP_TABLE,
            sa.Column("fr_id", sa.Integer, primary_key=True),
            sa.Column("reference", sa.String(120), nullable=True),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("amount", sa.Float, nullable=True),
            sa.Column("status", sa.String(50), nullable=True),
            sa.Column("cleaned_at", sa.DateTime, server_default=sa.func.now()),
        )

    rows = bind.execute(sa.text(
        """
        SELECT id, reference, description, amount, status
          FROM financial_records
         WHERE deleted_at IS NULL
           AND status IN ('pendente', 'vencido')
           AND (reference LIKE 'po_payment:%' OR reference LIKE 'order_payment:%')
        """
    )).fetchall()

    now = datetime.utcnow()
    cancels = 0
    for fr_id, ref, desc, amount, status in rows:
        prefix, _, pid_str = ref.partition(":")
        table = _TABLE_BY_PREFIX.get(prefix)
        if not table:
            continue
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        exists = bind.execute(
            sa.text(f"SELECT 1 FROM {table} WHERE id = :i"), {"i": pid}
        ).scalar()
        if exists:
            continue  # parcela existe — nao e orfao
        # backup de cautela (so insere se ainda nao houver registro)
        have = bind.execute(
            sa.text(f"SELECT 1 FROM {BACKUP_TABLE} WHERE fr_id = :i"), {"i": fr_id}
        ).scalar()
        if not have:
            bind.execute(
                sa.text(
                    f"""
                    INSERT INTO {BACKUP_TABLE}
                        (fr_id, reference, description, amount, status)
                    VALUES (:i, :r, :d, :a, :s)
                    """
                ),
                {"i": fr_id, "r": ref, "d": desc, "a": amount, "s": status},
            )
        bind.execute(
            sa.text("UPDATE financial_records SET deleted_at = :n WHERE id = :i"),
            {"n": now, "i": fr_id},
        )
        cancels += 1
    print(f"[cancel_orphan_payment_financials] {cancels} lancamento(s) orfao(s) cancelado(s)")


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if BACKUP_TABLE not in insp.get_table_names():
        return
    for (fr_id,) in bind.execute(sa.text(f"SELECT fr_id FROM {BACKUP_TABLE}")).fetchall():
        bind.execute(
            sa.text("UPDATE financial_records SET deleted_at = NULL WHERE id = :i"),
            {"i": fr_id},
        )
