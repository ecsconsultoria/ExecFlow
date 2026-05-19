"""FinancialEntry — ledger unificado V4.

Substitui gradualmente FinancialRecord (legacy).
Suporta entradas de receita, custo e transferência, com ou sem vínculo a OS.
"""
from ..extensions import db
from .base import TimestampMixin

ENTRY_TYPES      = ("revenue", "cost", "transfer")
ENTRY_STATUSES   = ("pendente", "aprovado", "pago", "parcial", "cancelado", "vencido")


class FinancialEntry(db.Model, TimestampMixin):
    __tablename__ = "financial_entries"

    id               = db.Column(db.Integer, primary_key=True)
    company_id       = db.Column(db.Integer, db.ForeignKey("companies.id"),      nullable=False)
    service_order_id = db.Column(db.Integer, db.ForeignKey("service_orders.id"), nullable=True)
    created_by       = db.Column(db.Integer, db.ForeignKey("users.id"),          nullable=True)

    type        = db.Column(db.String(50), nullable=False)   # revenue | cost | transfer
    category    = db.Column(db.String(100))
    description = db.Column(db.String(500))
    amount      = db.Column(db.Float, nullable=False)
    status      = db.Column(db.String(50), default="pendente")

    due_date       = db.Column(db.Date)
    paid_date      = db.Column(db.Date)
    payment_method = db.Column(db.String(50))
    reference      = db.Column(db.String(200))
    notes          = db.Column(db.Text)

    def __repr__(self):
        return f"<FinancialEntry {self.type} R${self.amount:.2f} {self.status}>"
