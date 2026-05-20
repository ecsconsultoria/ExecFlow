"""models/order.py — Pedido (Order): camada comercial entre Orçamento e OS.

Fluxo de status:
  novo → aberto → faturado → fechado
                ↘ cancelado (de qualquer status exceto fechado)

Relacionamentos:
  Order → OrderItem[]  (cópia dos itens do Orçamento)
  Order → OrderPayment[]  (parcelas de cobrança)
  Order ←→ Quote (backref quote.order, uselist=False)
  Order ←→ ServiceOrder (via quote_id — sem FK direta por ora)
"""

from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin

ORDER_STATUSES = ("novo", "aberto", "faturado", "fechado", "cancelado")


class Order(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "orders"

    id         = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    client_id  = db.Column(db.Integer, db.ForeignKey("clients.id"),   nullable=True)
    quote_id   = db.Column(db.Integer, db.ForeignKey("quotes.id"),    nullable=True)

    number  = db.Column(db.String(50), unique=True, nullable=False)
    status  = db.Column(db.String(50), default="novo", nullable=False)

    # Dados de contato (copiados do Orçamento)
    client_name  = db.Column(db.String(200))
    contact_name = db.Column(db.String(200))
    email        = db.Column(db.String(200))
    phone        = db.Column(db.String(50))
    celular      = db.Column(db.String(50))

    language     = db.Column(db.String(10),  default="pt")
    billing_type = db.Column(db.String(50),  default="recibo")
    obs          = db.Column(db.Text)
    total_amount = db.Column(db.Float,       default=0)

    payment_method = db.Column(db.String(50))
    payment_terms  = db.Column(db.String(100))

    # Campos de datas operacionais
    emission_date     = db.Column(db.Date,     nullable=True)   # data de emissão
    delivery_datetime = db.Column(db.DateTime, nullable=True)   # data de entrega

    # Ajustes financeiros (afetam o total final)
    discount_type      = db.Column(db.String(5), default="R$")  # 'R$' ou '%'
    discount_value     = db.Column(db.Float,     default=0)
    freight_amount     = db.Column(db.Float,     default=0)
    other_costs_amount = db.Column(db.Float,     default=0)

    # Faturamento
    invoice_number   = db.Column(db.String(100))
    invoiced_at      = db.Column(db.DateTime, nullable=True)
    invoice_due_date = db.Column(db.Date,     nullable=True)

    # Timestamps de transição de status
    opened_at    = db.Column(db.DateTime, nullable=True)
    closed_at    = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancel_reason = db.Column(db.Text)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Relacionamentos
    items    = db.relationship(
        "OrderItem",    backref="order", lazy="select",
        cascade="all, delete-orphan", order_by="OrderItem.sort_order",
    )
    payments = db.relationship(
        "OrderPayment", backref="order", lazy="select",
        cascade="all, delete-orphan", order_by="OrderPayment.installment_no",
    )
    company = db.relationship("Company", foreign_keys=[company_id])
    client  = db.relationship("Client",  foreign_keys=[client_id])
    quote   = db.relationship(
        "Quote", foreign_keys=[quote_id],
        backref=db.backref("order", uselist=False),
    )

    # ──────────────────────────────────────────────────────────────
    # Helpers financeiros
    # ──────────────────────────────────────────────────────────────

    @property
    def computed_total(self) -> float:
        """Total final após desconto, frete e outros custos."""
        base = self.total_amount or 0
        disc = self.discount_value or 0
        if (self.discount_type or "R$") == "%":
            disc_amount = base * (disc / 100)
        else:
            disc_amount = disc
        return base - disc_amount + (self.freight_amount or 0) + (self.other_costs_amount or 0)

    def total_paid(self) -> float:
        return sum(p.paid_amount or 0 for p in self.payments)

    def total_pending(self) -> float:
        return self.computed_total - self.total_paid()

    def __repr__(self):
        return f"<Order {self.number}>"


class OrderItem(db.Model, TimestampMixin):
    __tablename__ = "order_items"

    id       = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False,
    )
    service_id  = db.Column(db.Integer, db.ForeignKey("services.id"),           nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("vehicle_categories.id"), nullable=True)

    description         = db.Column(db.String(500))
    vehicle_description = db.Column(db.String(200))
    quantity            = db.Column(db.Integer, default=1)
    unit_price          = db.Column(db.Float,   default=0)
    total_price         = db.Column(db.Float,   default=0)
    sort_order          = db.Column(db.Integer, default=0)
    driver_name         = db.Column(db.String(200))
    state_code          = db.Column(db.String(10))
    ref_note            = db.Column(db.String(500))

    category = db.relationship("VehicleCategory", foreign_keys=[category_id], lazy="select")

    def __repr__(self):
        return f"<OrderItem {self.id} order={self.order_id}>"


class OrderPayment(db.Model, TimestampMixin):
    """Parcela de cobrança — controla quando o cliente deve pagar e se já pagou."""
    __tablename__ = "order_payments"

    id             = db.Column(db.Integer, primary_key=True)
    order_id       = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False,
    )
    installment_no = db.Column(db.Integer, default=1)
    due_date       = db.Column(db.Date,     nullable=True)
    amount         = db.Column(db.Float,    default=0)
    notes          = db.Column(db.Text)

    # Dados de baixa
    paid_at     = db.Column(db.DateTime, nullable=True)
    paid_amount = db.Column(db.Float,    default=0)
    paid_by     = db.Column(db.Integer,  db.ForeignKey("users.id"), nullable=True)

    @property
    def balance(self) -> float:
        return (self.amount or 0) - (self.paid_amount or 0)

    @property
    def is_paid(self) -> bool:
        return self.balance <= 0

    def __repr__(self):
        return f"<OrderPayment {self.installment_no} order={self.order_id}>"
