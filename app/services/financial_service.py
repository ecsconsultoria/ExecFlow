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
    """Soft-deleta todos os FinancialRecords vinculados a uma lista de pagamentos.

    Args:
        payments: lista de OrderPayment ou POPayment
        prefix: "order_payment" ou "po_payment"

    Returns:
        Número de registros soft-deletados.
    """
    refs = _build_financial_refs(payments, prefix)
    if not refs:
        return 0
    recs = FinancialRecord.query.filter(
        FinancialRecord.reference.in_(refs),
        FinancialRecord.deleted_at.is_(None),
    ).all()
    for r in recs:
        r.soft_delete()
    return len(recs)


