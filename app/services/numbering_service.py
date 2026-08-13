"""numbering_service.py — Geração centralizada de numeração sequencial para documentos ERP.

Padrão: PREFIX-AAMMDD-NNN  (ex: RFQ-260519-001, SO-260519-001, OS-260519-001)
- Segurança: filtra por company_id e prefixo do dia para sequência diária
- Thread-safe: depende de flush/commit do SQLAlchemy antes de chamar
"""

from ..utils import now_br


def _next_seq(model_class, field_name: str, company_id: int, prefix: str) -> str:
    """Busca o último registro com o prefixo do dia e retorna o próximo número."""
    last = (
        model_class.query
        .filter_by(company_id=company_id)
        .filter(getattr(model_class, field_name).like(f"{prefix}-%"))
        .order_by(model_class.id.desc())
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(getattr(last, field_name).split("-")[-1]) + 1
        except (ValueError, IndexError):
            pass
    return f"{prefix}-{seq:03d}"


def next_rfq(company_id: int) -> str:
    """Próximo número de Orçamento: RFQ-AAMMDD-NNN."""
    from ..models.quote import Quote
    prefix = "RFQ-" + now_br().strftime("%y%m%d")
    return _next_seq(Quote, "number", company_id, prefix)


def next_order(company_id: int) -> str:
    """Próximo número de Pedido: SO-AAMMDD-NNN."""
    from ..models.order import Order
    prefix = "SO-" + now_br().strftime("%y%m%d")
    return _next_seq(Order, "number", company_id, prefix)


def next_os(company_id: int) -> str:
    """Próximo código de Ordem de Serviço: OS-AAMMDD-NNN."""
    from ..models.service_order import ServiceOrder
    prefix = "OS-" + now_br().strftime("%y%m%d")
    return _next_seq(ServiceOrder, "code", company_id, prefix)


def next_po(company_id: int) -> str:
    """Próximo número de Purchase Order: PO-AAMMDD-NNN."""
    from ..models.purchase_order import PurchaseOrder
    prefix = "PO-" + now_br().strftime("%y%m%d")
    return _next_seq(PurchaseOrder, "number", company_id, prefix)


def next_receipt(company_id: int) -> str:
    """Próximo número de Recibo de Pagamento: REC-AAMMDD-NNN."""
    from ..models.payment_receipt import PaymentReceipt
    prefix = "REC-" + now_br().strftime("%y%m%d")
    return _next_seq(PaymentReceipt, "receipt_number", company_id, prefix)
