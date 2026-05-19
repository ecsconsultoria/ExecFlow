"""RevenueEntry — receitas da OS (contas a receber).

Cada OS gera automaticamente um RevenueEntry com o valor do orçamento aprovado.
Registros adicionais podem ser criados para cobranças extras.
"""
from ..extensions import db
from .base import TimestampMixin

REVENUE_STATUSES = ("pendente", "parcial", "pago", "cancelado", "vencido")
BILLING_TYPES    = ("recibo", "nf", "cartao", "nf_cartao")


class RevenueEntry(db.Model, TimestampMixin):
    __tablename__ = "revenue_entries"

    id               = db.Column(db.Integer, primary_key=True)
    service_order_id = db.Column(db.Integer, db.ForeignKey("service_orders.id"), nullable=True)
    company_id       = db.Column(db.Integer, db.ForeignKey("companies.id"),      nullable=False)
    client_id        = db.Column(db.Integer, db.ForeignKey("clients.id"),        nullable=True)
    created_by       = db.Column(db.Integer, db.ForeignKey("users.id"),          nullable=True)

    amount         = db.Column(db.Float, nullable=False)
    billing_type   = db.Column(db.String(50), default="recibo")
    status         = db.Column(db.String(50), default="pendente")
    description    = db.Column(db.String(500))
    due_date       = db.Column(db.Date)
    paid_date      = db.Column(db.Date)
    payment_method = db.Column(db.String(50))
    reference      = db.Column(db.String(200))
    notes          = db.Column(db.Text)

    client = db.relationship("Client", foreign_keys=[client_id], lazy="joined")

    def __repr__(self):
        return f"<RevenueEntry R${self.amount:.2f} {self.status}>"
