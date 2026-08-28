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


