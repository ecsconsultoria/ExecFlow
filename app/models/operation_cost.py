"""OperationCost — custos operacionais da OS.

Todos os custos (motorista, fornecedor, pedágio, estacionamento, combustível, etc.)
são registrados aqui com cost_type enum para BI/relatórios futuros.

margin = revenue - sum(OperationCost.amount)
"""
from ..extensions import db
from .base import TimestampMixin

COST_TYPES = (
    "supplier",      # repasse ao fornecedor
    "toll",          # pedágio
    "parking",       # estacionamento
    "airport_fee",   # adicional aeroporto
    "receptive",     # receptivo / meet & greet
    "fuel",          # combustível
    "extra_hour",    # hora extra
    "accommodation", # hospedagem
    "food",          # alimentação
    "misc",          # outros
)

COST_TYPE_LABELS = {
    "supplier":      "Fornecedor",
    "toll":          "Pedágio",
    "parking":       "Estacionamento",
    "airport_fee":   "Adicional Aeroporto",
    "receptive":     "Receptivo",
    "fuel":          "Combustível",
    "extra_hour":    "Hora Extra",
    "accommodation": "Hospedagem",
    "food":          "Alimentação",
    "misc":          "Outros",
}


class OperationCost(db.Model, TimestampMixin):
    __tablename__ = "operation_costs"

    id               = db.Column(db.Integer, primary_key=True)
    service_order_id = db.Column(db.Integer, db.ForeignKey("service_orders.id"), nullable=False)
    company_id       = db.Column(db.Integer, db.ForeignKey("companies.id"),      nullable=False)
    created_by       = db.Column(db.Integer, db.ForeignKey("users.id"),          nullable=True)

    cost_type    = db.Column(db.String(50), nullable=False)  # COST_TYPES enum
    amount       = db.Column(db.Float, nullable=False)
    description  = db.Column(db.String(500))
    reference    = db.Column(db.String(200))
    notes        = db.Column(db.Text)

    paid         = db.Column(db.Boolean, default=False)
    paid_date    = db.Column(db.Date)
    payment_method = db.Column(db.String(50))

    @property
    def cost_type_label(self):
        return COST_TYPE_LABELS.get(self.cost_type, self.cost_type)

    def __repr__(self):
        return f"<OperationCost {self.cost_type} R${self.amount:.2f} os={self.service_order_id}>"
