"""payment_receipt.py — Recibo de Pagamento (Payment Receipt).

Documento de emissão imutável: registra que um recibo oficial (REC-AAMMDD-NNN)
foi emitido para uma parcela paga de um Sales Order. A geração do PDF é sob
demanda e somente leitura em relação às finanças — esta tabela NÃO representa
lançamento financeiro, apenas a numeração/documento emitido.

- Sem SoftDeleteMixin: recibo é documento histórico; não há fluxo de exclusão.
- payment_id UNIQUE: 1 recibo oficial por parcela (regeneração reutiliza o número).
"""

from ..extensions import db
from ..utils import now_br
from .base import TimestampMixin


class PaymentReceipt(db.Model, TimestampMixin):
    __tablename__ = "payment_receipts"

    id             = db.Column(db.Integer, primary_key=True)
    company_id     = db.Column(db.Integer, db.ForeignKey("companies.id"),      nullable=False, index=True)
    order_id       = db.Column(db.Integer, db.ForeignKey("orders.id"),         nullable=False, index=True)
    payment_id     = db.Column(db.Integer, db.ForeignKey("order_payments.id"), nullable=False, unique=True)
    receipt_number = db.Column(db.String(50), nullable=False, unique=True)
    issued_at      = db.Column(db.DateTime, default=now_br, nullable=False)
    issued_by      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    order   = db.relationship("Order",       foreign_keys=[order_id])
    payment = db.relationship("OrderPayment", foreign_keys=[payment_id])
    company = db.relationship("Company",     foreign_keys=[company_id])
    issuer  = db.relationship("User",        foreign_keys=[issued_by], lazy="joined")

    def __repr__(self):
        return f"<PaymentReceipt {self.receipt_number}>"
