"""ServiceOrder — núcleo operacional do ERP V4.

Representa a Ordem de Serviço (OS) gerada automaticamente a partir de um Booking
confirmado. É a entidade central visível para as equipes de dispatch e operações.

Código sequencial: OS-2026-0001
"""
from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin

OS_STATUSES = (
    "criado",
    "agendado",
    "atribuido",
    "confirmado_cliente",
    "em_execucao",
    "finalizado",
    "cancelado",
)


class ServiceOrder(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "service_orders"

    # ── Identificação ─────────────────────────────────────────────────────────
    id         = db.Column(db.Integer, primary_key=True)
    code       = db.Column(db.String(50), unique=True, nullable=False)  # OS-2026-0001
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"),     nullable=True)

    # ── Vínculos comerciais ────────────────────────────────────────────────────
    booking_id  = db.Column(db.Integer, db.ForeignKey("bookings.id"),  nullable=True)
    quote_id    = db.Column(db.Integer, db.ForeignKey("quotes.id"),    nullable=True)
    client_id   = db.Column(db.Integer, db.ForeignKey("clients.id"),   nullable=True)
    service_id  = db.Column(db.Integer, db.ForeignKey("services.id"),  nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("vehicle_categories.id"), nullable=True)

    # ── Dados do passageiro ───────────────────────────────────────────────────
    passenger_name  = db.Column(db.String(200))
    passenger_phone = db.Column(db.String(50))
    passenger_email = db.Column(db.String(200))
    pax_count       = db.Column(db.Integer, default=1)
    language        = db.Column(db.String(10), default="pt")

    # ── Dados operacionais ────────────────────────────────────────────────────
    pickup_datetime      = db.Column(db.DateTime)
    pickup_location      = db.Column(db.Text)
    dropoff_location     = db.Column(db.Text)
    flight_number        = db.Column(db.String(50))
    vehicle_description  = db.Column(db.String(200))
    notes                = db.Column(db.Text)

    # ── Status ────────────────────────────────────────────────────────────────
    status = db.Column(db.String(50), default="criado")

    # ── Atribuição atual (snapshot — histórico em ServiceOrderAssignment) ─────
    assigned_driver_id      = db.Column(db.Integer, db.ForeignKey("drivers.id"),   nullable=True)
    assigned_vehicle_id     = db.Column(db.Integer, db.ForeignKey("vehicles.id"),  nullable=True)
    supplier_id             = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    supplier_driver_name    = db.Column(db.String(200))
    supplier_vehicle_desc   = db.Column(db.String(200))
    supplier_contact        = db.Column(db.String(200))

    # ── Controle operacional ──────────────────────────────────────────────────
    internal_notes       = db.Column(db.Text)
    dispatch_notes       = db.Column(db.Text)
    driver_info_sent     = db.Column(db.Boolean, default=False)
    driver_info_sent_at  = db.Column(db.DateTime)
    executed_at          = db.Column(db.DateTime)
    closed_at            = db.Column(db.DateTime)

    # ── Financeiro operacional (denormalizado para performance de listagem) ───
    revenue_amount     = db.Column(db.Float, default=0.0)
    total_cost_amount  = db.Column(db.Float, default=0.0)
    supplier_amount    = db.Column(db.Float, default=0.0)
    margin_amount      = db.Column(db.Float, default=0.0)

    # ── Relacionamentos ───────────────────────────────────────────────────────
    assignments  = db.relationship("ServiceOrderAssignment", backref="service_order",
                                   lazy="dynamic", cascade="all, delete-orphan",
                                   order_by="ServiceOrderAssignment.assigned_at.desc()")
    events       = db.relationship("ServiceOrderEvent",      backref="service_order",
                                   lazy="dynamic", cascade="all, delete-orphan",
                                   order_by="ServiceOrderEvent.created_at.asc()")
    costs        = db.relationship("OperationCost",  backref="service_order",
                                   lazy="dynamic", cascade="all, delete-orphan")
    revenue_entries   = db.relationship("RevenueEntry",   backref="service_order",
                                        lazy="dynamic", cascade="all, delete-orphan")
    supplier_payments = db.relationship("SupplierPayment", backref="service_order",
                                        lazy="dynamic", cascade="all, delete-orphan")
    financial_entries = db.relationship("FinancialEntry", backref="service_order",
                                        lazy="dynamic", cascade="all, delete-orphan")

    assigned_driver  = db.relationship("Driver",  foreign_keys=[assigned_driver_id],  lazy="joined")
    assigned_vehicle = db.relationship("Vehicle", foreign_keys=[assigned_vehicle_id], lazy="joined")
    quote            = db.relationship("Quote",   foreign_keys=[quote_id],            lazy="joined")

    @property
    def status_label(self):
        labels = {
            "criado":             "Criado",
            "agendado":           "Agendado",
            "atribuido":          "Atribuído",
            "confirmado_cliente": "Confirmado",
            "em_execucao":        "Em Execução",
            "finalizado":         "Finalizado",
            "cancelado":          "Cancelado",
        }
        return labels.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {
            "criado":             "slate",
            "agendado":           "blue",
            "atribuido":          "violet",
            "confirmado_cliente": "cyan",
            "em_execucao":        "amber",
            "finalizado":         "green",
            "cancelado":          "red",
        }
        return colors.get(self.status, "slate")

    def recalculate_margin(self):
        """margin = revenue - total_operational_costs (includes supplier costs)."""
        self.total_cost_amount = sum(c.amount for c in self.costs if not getattr(c, 'is_deleted', False))
        self.margin_amount = round((self.revenue_amount or 0) - (self.total_cost_amount or 0), 2)

    def __repr__(self):
        return f"<ServiceOrder {self.code}>"
