"""models/order.py — Pedido (Order): camada comercial entre Orçamento e OS.

Fluxo de status:
  novo → aberto → faturado → concluido
                ↘ cancelado (de qualquer status exceto concluido)

Relacionamentos:
  Order → OrderItem[]  (cópia dos itens do Orçamento)
  Order → OrderPayment[]  (parcelas de cobrança)
  Order ←→ Quote (backref quote.order, uselist=False)
  Order ←→ ServiceOrder (via quote_id — sem FK direta por ora)
"""

from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin

ORDER_STATUSES = ("novo", "aberto", "faturado", "concluido", "cancelado", "excluido")


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
    usd_rate     = db.Column(db.Float,       nullable=True)  # cotação R$/USD p/ PDF em inglês

    payment_method = db.Column(db.String(50))
    payment_terms  = db.Column(db.String(100))

    # Campos de datas operacionais
    emission_date     = db.Column(db.Date,     nullable=True)   # data de emissão
    delivery_datetime = db.Column(db.DateTime, nullable=True)   # data de entrega

    # Dados operacionais (motorista, veículo, passageiro)
    driver_name      = db.Column(db.String(200))
    driver_phone     = db.Column(db.String(50))
    vehicle_model    = db.Column(db.String(200))
    vehicle_plate    = db.Column(db.String(20))
    pickup_location  = db.Column(db.Text)
    dropoff_location = db.Column(db.Text)
    passenger_name   = db.Column(db.String(200))
    passenger_phone  = db.Column(db.String(50))
    flight_number    = db.Column(db.String(50))
    pax_count        = db.Column(db.Integer)
    vehicle_description = db.Column(db.String(200))  # Observações operacionais

    # Ajustes financeiros (afetam o total final)
    discount_type      = db.Column(db.String(5), default="R$")  # 'R$' ou '%'
    discount_value     = db.Column(db.Float,     default=0)
    freight_amount      = db.Column(db.Float,     default=0)
    other_costs_amount = db.Column(db.Float,     default=0)
    other_costs_label  = db.Column(db.String(200), default="")

    # Margem operacional (SO vs POs vinculadas)
    total_po_cost = db.Column(db.Float, default=0.0, nullable=True)   # soma das POs não-canceladas
    margin_amount = db.Column(db.Float, default=0.0, nullable=True)   # receita − custo PO

    @property
    def margin_pct(self) -> float:
        """Percentual de margem sobre a receita."""
        revenue = self.computed_total or 0.0
        if not revenue:
            return 0.0
        cost = self.total_po_cost or 0.0
        return round((revenue - cost) / revenue * 100, 1)

    # Faturamento
    invoice_number   = db.Column(db.String(100))
    invoiced_at      = db.Column(db.DateTime, nullable=True)
    invoice_due_date = db.Column(db.Date,     nullable=True)

    # Timestamps de transição de status
    opened_at    = db.Column(db.DateTime, nullable=True)
    closed_at    = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancel_reason = db.Column(db.Text)
    reopened_at  = db.Column(db.DateTime, nullable=True)

    created_by   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    opened_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    invoiced_by  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    closed_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    cancelled_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reopened_by  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

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
        backref=db.backref("orders", uselist=True),
    )
    creator   = db.relationship("User", foreign_keys=[created_by],   lazy="joined")
    opener    = db.relationship("User", foreign_keys=[opened_by],    lazy="joined")
    invoicer  = db.relationship("User", foreign_keys=[invoiced_by],  lazy="joined")
    closer    = db.relationship("User", foreign_keys=[closed_by],    lazy="joined")
    canceller = db.relationship("User", foreign_keys=[cancelled_by], lazy="joined")
    reopener  = db.relationship("User", foreign_keys=[reopened_by],  lazy="joined")

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

    @property
    def status_label(self) -> str:
        labels = {
            "novo":      "Novo",
            "aberto":    "Aberto",
            "faturado":  "Faturado",
            "concluido": "Conclu\u00eddo",
            "cancelado": "Cancelado",
            "excluido":  "Exclu\u00eddo",
        }
        return labels.get(self.status, self.status)

    @property
    def status_color(self) -> str:
        colors = {
            "novo":      "sky",
            "aberto":    "blue",
            "faturado":  "amber",
            "concluido": "emerald",
            "cancelado": "red",
            "excluido":  "slate",
        }
        return colors.get(self.status, "slate")

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

    # Dados operacionais por item (SO)
    op_driver_name      = db.Column(db.String(200))
    op_driver_phone     = db.Column(db.String(50))
    op_vehicle_model    = db.Column(db.String(200))
    op_vehicle_plate    = db.Column(db.String(20))
    op_pickup_datetime  = db.Column(db.DateTime, nullable=True)
    op_pickup_location  = db.Column(db.Text)
    op_dropoff_location = db.Column(db.Text)
    op_passenger_name   = db.Column(db.String(200))
    op_passenger_phone  = db.Column(db.String(50))
    op_flight_number    = db.Column(db.String(50))
    op_notes            = db.Column(db.String(500))

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
