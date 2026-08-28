"""FinancialService — registro financeiro (legado) + operações de cascade.

Fornece funções compartilhadas para manipulação de FinancialRecords
vinculados a pagamentos de Orders e PurchaseOrders.
"""
import logging
from ..models.financial import FinancialRecord, AccountReceivable
from ..extensions import db

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Cascade financeiro — unificado (extraído de 3 locais duplicados)
# ─────────────────────────────────────────────────────────────────────────────

def _build_financial_refs(payments, prefix: str) -> list[str]:
    """Constrói lista de references para FinancialRecord a partir de pagamentos."""
    return [f"{prefix}:{p.id}" for p in payments]


def void_payment_financial_records(payments, prefix: str) -> int:
    """Soft-deleta os FinancialRecords PENDENTES vinculados a pagamentos.

    Regra da Etapa 2: lançamentos de pagamentos JÁ REALIZADOS (status "pago")
    são histórico financeiro e NÃO podem ser apagados automaticamente pela
    exclusão/cancelamento da origem (SO/PO). Somente pendentes são voidados.

    Args:
        payments: lista de OrderPayment ou POPayment
        prefix: "order_payment" ou "po_payment"

    Returns:
        Número de registros soft-deletados (exclui os preservados por estarem pagos).
    """
    refs = _build_financial_refs(payments, prefix)
    if not refs:
        return 0
    recs = FinancialRecord.query.filter(
        FinancialRecord.reference.in_(refs),
        FinancialRecord.deleted_at.is_(None),
    ).all()
    voided = 0
    for r in recs:
        if (r.status or "") == "pago":
            continue  # histórico pago preservado (Etapa 2)
        r.soft_delete()
        voided += 1
    return voided


# ─────────────────────────────────────────────────────────────────────────────
# Etapa 6 — restauração CONTROLADA, registro a registro (nunca em lote)
# ─────────────────────────────────────────────────────────────────────────────

class RestorationBlocked(Exception):
    """Restauração negada por não atender aos critérios de segurança."""


def restore_financial_record(record_id: int, company_id: int) -> FinancialRecord:
    """Remove SOMENTE a marcação de soft-delete de UM FinancialRecord.

    Guardas (qualquer falha aborta sem alterar nada):
      * registro existe, pertence à company informada e está soft-deletado;
      * reference segue os padrões order_payment:/po_payment:/expense:;
      * para pagamentos: a parcela existe E está efetivamente paga;
      * valor do FR coincide com o valor pago (sem recálculo automático);
      * NÃO existe FinancialRecord ATIVO com a mesma reference.

    Preserva integralmente: id, valor, datas, status, reference, company_id
    e todos os demais campos. Não faz commit — o chamador controla a transação.
    """
    fr = (FinancialRecord.query
          .filter_by(id=record_id, company_id=company_id)
          .first())
    if fr is None:
        raise RestorationBlocked("Registro inexistente para a empresa informada")
    if fr.deleted_at is None:
        raise RestorationBlocked("Registro não está soft-deletado")

    ref = fr.reference or ""
    if ref.startswith("order_payment:") or ref.startswith("po_payment:"):
        prefix, pid_s = ref.split(":", 1)
        try:
            pid = int(pid_s)
        except ValueError:
            raise RestorationBlocked("Reference inválida")
        if prefix == "order_payment":
            from ..models.order import OrderPayment
            payment = db.session.get(OrderPayment, pid)
        else:
            from ..models.purchase_order import POPayment
            payment = db.session.get(POPayment, pid)
        if payment is None:
            raise RestorationBlocked("Parcela inexistente — não restaurar")
        if not getattr(payment, "paid_at", None):
            raise RestorationBlocked("Parcela não paga — não restaurar como realizado")
        if abs((fr.amount or 0.0) - (payment.paid_amount or 0.0)) > 0.005:
            raise RestorationBlocked("Divergência de valor — não restaurar automaticamente")
    elif ref.startswith("expense:"):
        pass  # despesa própria; validada pela ausência de duplicata abaixo
    else:
        raise RestorationBlocked("Reference fora dos padrões — requer revisão manual")

    dup = (FinancialRecord.query
           .filter(FinancialRecord.reference == ref,
                   FinancialRecord.deleted_at.is_(None),
                   FinancialRecord.id != fr.id)
           .first())
    if dup is not None:
        raise RestorationBlocked("Duplicidade ativa — não restaurar")

    fr.deleted_at = None  # única alteração: remove o soft-delete
    return fr


def restore_and_audit(record_id: int, company_id: int, user_id: int) -> FinancialRecord:
    """Restaura + auditoria + commit atômico; rollback total em falha."""
    from ..utils.audit import log_activity

    try:
        fr = restore_financial_record(record_id, company_id)
        log_activity("financial", fr.id, fr.company_id,
                     f"FinancialRecord RESTAURADO (Etapa 6) ref={fr.reference} "
                     f"tipo={fr.type} valor={fr.amount:.2f}", user_id)
        db.session.commit()
        return fr
    except Exception:
        db.session.rollback()
        raise


