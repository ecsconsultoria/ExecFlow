"""PurchaseOrder — camada de compras/custos do ERP V4.

Representa a Ordem de Compra (PO) emitida para um fornecedor terceirizado
como contraparte operacional de um Pedido de Venda (SO).

Numeração: PO-AAMMDD-NNN
Fluxo de status: rascunho → aberto → aprovado → em_execucao → concluido → faturado / cancelado
Papel financeiro: despesa / contas a pagar
"""
from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin

PO_STATUSES = (
    "rascunho",      # PO criada, ainda não enviada ao fornecedor
    "aberto",        # PO aberta para processamento
    "enviado",       # LEGACY: manter compatibilidade com registros antigos
    "aprovado",      # Fornecedor confirmou
    "em_execucao",   # Serviço em andamento
    "concluido",     # Serviço executado e encerrado
    "faturado",      # Nota fiscal do fornecedor recebida / faturado
    "pago",          # Todas as parcelas quitadas (Concluído)
    "cancelado",     # Cancelada
    "excluido",      # Excluído (soft-delete — preserva histórico)
)


class PurchaseOrder(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "purchase_orders"

    # ── Identificação ─────────────────────────────────────────────────────────
    id         = db.Column(db.Integer, primary_key=True)
    number     = db.Column(db.String(50), unique=True, nullable=False)  # PO-AAMMDD-NNN
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"),     nullable=True)

    # ── Vínculos ─────────────────────────────────────────────────────────────
    service_order_id = db.Column(db.Integer, db.ForeignKey("service_orders.id"), nullable=True)
    order_id         = db.Column(db.Integer, db.ForeignKey("orders.id"),         nullable=True)
    quote_id         = db.Column(db.Integer, db.ForeignKey("quotes.id"),         nullable=True)

    # ── Fornecedor & Serviço ──────────────────────────────────────────────────
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    service_id  = db.Column(db.Integer, db.ForeignKey("services.id"),  nullable=True)

    # ── Dados do passageiro (condicional: requires_passenger) ─────────────────
    passenger_name  = db.Column(db.String(200))
    passenger_phone = db.Column(db.String(50))
    pax_count       = db.Column(db.Integer, default=1)

    # ── Dados de rota (condicional: requires_route) ───────────────────────────
    pickup_datetime  = db.Column(db.DateTime)
    pickup_location  = db.Column(db.Text)
    dropoff_location = db.Column(db.Text)
    flight_number    = db.Column(db.String(50))

    # ── Dados de veículo (condicional: requires_vehicle) ─────────────────────
    vehicle_category_id = db.Column(db.Integer, db.ForeignKey("vehicle_categories.id"), nullable=True)
    vehicle_model       = db.Column(db.String(200))
    vehicle_description = db.Column(db.String(200))
    vehicle_plate       = db.Column(db.String(20))
    driver_name         = db.Column(db.String(200))
    driver_phone        = db.Column(db.String(50))

    # ── Financeiro — despesa / contas a pagar ────────────────────────────────
    amount           = db.Column(db.Float, default=0.0)
    payment_method   = db.Column(db.String(50))
    payment_terms    = db.Column(db.String(50))
    payment_due_date = db.Column(db.Date)
    paid_at          = db.Column(db.DateTime)

    # Ajustes financeiros (afetam o total final)
    discount_type      = db.Column(db.String(5),   default="R$")   # 'R$' ou '%'
    discount_value     = db.Column(db.Float,        default=0)
    freight_amount     = db.Column(db.Float,        default=0)
    other_costs_amount = db.Column(db.Float,        default=0)
    other_costs_label  = db.Column(db.String(200),  default="")

    # ── Status & controle ────────────────────────────────────────────────────
    status         = db.Column(db.String(50), default="rascunho")
    notes          = db.Column(db.Text)
    internal_notes = db.Column(db.Text)
    sent_at        = db.Column(db.DateTime)
    approved_at    = db.Column(db.DateTime)
    concluded_at   = db.Column(db.DateTime)
    cancelled_at   = db.Column(db.DateTime)
    invoiced_at    = db.Column(db.DateTime)
    invoiced_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reopened_at    = db.Column(db.DateTime)
    reopened_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # ── Relacionamentos ───────────────────────────────────────────────────────
    creator          = db.relationship("User",           foreign_keys=[created_by],           lazy="joined")
    company          = db.relationship("Company",       foreign_keys=[company_id],           lazy="select")
    supplier         = db.relationship("Supplier",      foreign_keys=[supplier_id],         lazy="joined")
    service          = db.relationship("Service",       foreign_keys=[service_id],           lazy="joined")
    service_order    = db.relationship("ServiceOrder",  foreign_keys=[service_order_id],     lazy="joined")
    order            = db.relationship("Order",         foreign_keys=[order_id],             lazy="joined",
                                       backref=db.backref("purchase_orders", lazy="select"))
    vehicle_category = db.relationship("VehicleCategory", foreign_keys=[vehicle_category_id], lazy="joined")
    payments         = db.relationship("POPayment",     back_populates="purchase_order",
                                       cascade="all, delete-orphan", lazy="dynamic",
                                       order_by="POPayment.installment_no")
    items            = db.relationship("POItem",        back_populates="purchase_order",
                                       cascade="all, delete-orphan", lazy="select",
                                       order_by="POItem.sort_order")

    @property
    def subtotal(self) -> float:
        """Soma dos itens + frete + outros custos, SEM desconto."""
        if self.items:
            base = sum(i.total_cost or 0 for i in self.items)
        else:
            base = self.amount or 0.0
        return base + (self.freight_amount or 0) + (self.other_costs_amount or 0)

    @property
    def computed_total(self) -> float:
        base = self.subtotal
        disc = self.discount_value or 0
        if (self.discount_type or "R$") == "%":
            disc_amount = base * (disc / 100)
        else:
            disc_amount = disc
        return base - disc_amount

    def total_paid(self) -> float:
        return sum(p.paid_amount or 0 for p in self.payments)

    def total_pending(self) -> float:
        return max(self.computed_total - self.total_paid(), 0)

    @property
    def status_label(self):
        labels = {
            "rascunho":    "Rascunho",
            "aberto":      "Aberto",
            "enviado":     "Aberto",
            "aprovado":    "Aprovado",
            "em_execucao": "Em Execução",
            "concluido":   "Concluído",
            "faturado":    "Faturado",
            "pago":        "Concluído",
            "cancelado":   "Cancelado",
            "excluido":    "Excluído",
        }
        return labels.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {
            "rascunho":    "slate",
            "aberto":      "blue",
            "enviado":     "blue",
            "aprovado":    "emerald",
            "em_execucao": "amber",
            "concluido":   "emerald",
            "faturado":    "amber",
            "pago":        "emerald",
            "cancelado":   "red",
            "excluido":    "slate",
        }
        return colors.get(self.status, "slate")

    def __repr__(self):
        return f"<PurchaseOrder {self.number}>"


class POPayment(db.Model, TimestampMixin):
    """Parcela de custo/despesa da PO — controla quando o fornecedor deve ser pago."""
    __tablename__ = "po_payments"

    id             = db.Column(db.Integer, primary_key=True)
    po_id          = db.Column(
        db.Integer, db.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False,
    )
    installment_no = db.Column(db.Integer, default=1)
    due_date       = db.Column(db.Date,    nullable=True)
    amount         = db.Column(db.Float,   default=0)
    notes          = db.Column(db.Text)

    # Dados de baixa
    paid_at     = db.Column(db.DateTime, nullable=True)
    paid_amount = db.Column(db.Float,    default=0)
    paid_by     = db.Column(db.Integer,  db.ForeignKey("users.id"), nullable=True)

    purchase_order = db.relationship("PurchaseOrder", back_populates="payments")

    @property
    def balance(self) -> float:
        return (self.amount or 0) - (self.paid_amount or 0)

    @property
    def is_paid(self) -> bool:
        return self.balance <= 0

    def __repr__(self):
        return f"<POPayment {self.installment_no} po={self.po_id}>"


class POItem(db.Model, TimestampMixin):
    """Linha de custo de uma PO (um item de serviço por linha)."""
    __tablename__ = "po_items"

    id     = db.Column(db.Integer, primary_key=True)
    po_id  = db.Column(
        db.Integer, db.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False,
    )
    service_id          = db.Column(db.Integer, db.ForeignKey("services.id"),           nullable=True)
    category_id         = db.Column(db.Integer, db.ForeignKey("vehicle_categories.id"), nullable=True)
    description         = db.Column(db.String(500))
    vehicle_description = db.Column(db.String(200))
    quantity            = db.Column(db.Integer, default=1)
    unit_cost           = db.Column(db.Float,   default=0)
    total_cost          = db.Column(db.Float,   default=0)
    sort_order          = db.Column(db.Integer, default=0)

    # Dados operacionais por item (PO) — espelha os campos do card global de PO
    op_pickup_datetime  = db.Column(db.DateTime, nullable=True)
    op_pickup_location  = db.Column(db.Text)
    op_dropoff_location = db.Column(db.Text)
    op_passenger_name   = db.Column(db.String(200))
    op_passenger_phone  = db.Column(db.String(50))
    op_flight_number    = db.Column(db.String(50))
    op_pax_count        = db.Column(db.Integer)
    op_notes            = db.Column(db.String(500))
    # Campos legados (não utilizados na UI atual do PO, mantidos por compatibilidade)
    op_driver_name      = db.Column(db.String(200))
    op_driver_phone     = db.Column(db.String(50))
    op_vehicle_model    = db.Column(db.String(200))
    op_vehicle_plate    = db.Column(db.String(20))

    purchase_order = db.relationship("PurchaseOrder", back_populates="items")
    service        = db.relationship("Service",         foreign_keys=[service_id],  lazy="joined")
    category       = db.relationship("VehicleCategory", foreign_keys=[category_id], lazy="joined")

    def __repr__(self):
        return f"<POItem {self.id} po={self.po_id}>"
