"""SupplierPayment — pagamentos devidos a fornecedores por OS.

Gerado automaticamente quando um fornecedor é atribuído a uma OS com valor negociado.
"""
from ..extensions import db
from .base import TimestampMixin

PAYMENT_STATUSES = ("pendente", "aprovado", "pago", "cancelado")


class SupplierPayment(db.Model, TimestampMixin):
    __tablename__ = "supplier_payments"

    id               = db.Column(db.Integer, primary_key=True)
    service_order_id = db.Column(db.Integer, db.ForeignKey("service_orders.id"), nullable=True)
    supplier_id      = db.Column(db.Integer, db.ForeignKey("suppliers.id"),      nullable=False)
    company_id       = db.Column(db.Integer, db.ForeignKey("companies.id"),      nullable=False)
    created_by       = db.Column(db.Integer, db.ForeignKey("users.id"),          nullable=True)

    amount         = db.Column(db.Float, nullable=False)
    status         = db.Column(db.String(50), default="pendente")
    description    = db.Column(db.String(500))
    due_date       = db.Column(db.Date)
    paid_date      = db.Column(db.Date)
    payment_method = db.Column(db.String(50))
    notes          = db.Column(db.Text)

    supplier = db.relationship("Supplier", foreign_keys=[supplier_id], lazy="joined")

    def __repr__(self):
        return f"<SupplierPayment supplier={self.supplier_id} R${self.amount:.2f} {self.status}>"
