"""Legacy financial models — kept for V3 backward compatibility.
New operational financials use: RevenueEntry, OperationCost, SupplierPayment, FinancialEntry.
"""
from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin

FINANCIAL_TYPES      = ("revenue", "cost")
FINANCIAL_CATEGORIES = (
    "receita_servico", "receita_adicional",
    "custo_motorista", "custo_fornecedor", "custo_operacional",
    "comissao", "imposto", "outro",
)
FINANCIAL_STATUSES = ("pendente", "aprovado", "pago", "parcial", "cancelado", "vencido")


class FinancialRecord(db.Model, TimestampMixin, SoftDeleteMixin):
    """LEGACY — migrating to FinancialEntry + OperationCost + RevenueEntry."""
    __tablename__ = "financial_records"

    id             = db.Column(db.Integer, primary_key=True)
    company_id     = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    quote_id       = db.Column(db.Integer, db.ForeignKey("quotes.id"),   nullable=True)
    type           = db.Column(db.String(50), nullable=False)
    category       = db.Column(db.String(100))
    description    = db.Column(db.String(500))
    amount         = db.Column(db.Float, nullable=False)
    status         = db.Column(db.String(50), default="pendente")
    emission_date  = db.Column(db.Date, nullable=True)   # data contábil (data de emissão do SO/PO)
    due_date       = db.Column(db.Date)
    paid_date      = db.Column(db.Date)
    payment_method = db.Column(db.String(50))
    reference      = db.Column(db.String(200))
    notes          = db.Column(db.Text)
    # Etapa 3A — vínculos opcionais com a nova fundação (NULL nos registros históricos;
    # nenhum backfill: somente lançamentos futuros preencherão).
    financial_category_id = db.Column(db.Integer, db.ForeignKey("financial_categories.id"), nullable=True)
    cost_center_id        = db.Column(db.Integer, db.ForeignKey("cost_centers.id"),          nullable=True)

    category_ref = db.relationship("FinancialCategory")
    cost_center  = db.relationship("CostCenter")

    def __repr__(self):
        return f"<FinancialRecord {self.type} R${self.amount:.2f}>"


class AccountReceivable(db.Model, TimestampMixin):
    """LEGACY — kept for backward compat."""
    __tablename__ = "accounts_receivable"

    id             = db.Column(db.Integer, primary_key=True)
    company_id     = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    quote_id       = db.Column(db.Integer, db.ForeignKey("quotes.id"),    nullable=True)
    client_id      = db.Column(db.Integer, db.ForeignKey("clients.id"),   nullable=True)
    amount         = db.Column(db.Float, nullable=False)
    amount_paid    = db.Column(db.Float, default=0)
    due_date       = db.Column(db.Date)
    paid_date      = db.Column(db.Date)
    status         = db.Column(db.String(50), default="pendente")
    payment_method = db.Column(db.String(50))
    notes          = db.Column(db.Text)

    def __repr__(self):
        return f"<AccountReceivable R${self.amount:.2f}>"
