from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin

BILLING_TYPES  = ("recibo", "nf", "cartao", "nf_cartao")
QUOTE_STATUSES = ("pendente", "aprovado", "reprovado", "pago", "reserva_confirmada", "cancelado", "excluido")


class Quote(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "quotes"

    id         = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    client_id  = db.Column(db.Integer, db.ForeignKey("clients.id"),   nullable=True)
    number     = db.Column(db.String(50), unique=True, nullable=False)

    client_name  = db.Column(db.String(200))
    contact_name = db.Column(db.String(200))
    email        = db.Column(db.String(200))
    phone        = db.Column(db.String(50))

    language      = db.Column(db.String(10), default="pt")
    billing_type  = db.Column(db.String(50), default="recibo")
    status        = db.Column(db.String(50), default="pendente")
    obs           = db.Column(db.Text)
    total_amount  = db.Column(db.Float, default=0)
    pdf_file      = db.Column(db.String(500))

    # Commercial payment (belongs to Quote, not Operation)
    payment_status  = db.Column(db.String(50))
    payment_method  = db.Column(db.String(50))
    payment_terms   = db.Column(db.String(100))
    payment_amount  = db.Column(db.Float)
    payment_pct     = db.Column(db.Integer)
    payment_paid_at = db.Column(db.DateTime)
    fiscal_document = db.Column(db.String(200))

    valid_until      = db.Column(db.Date, nullable=True)
    approved_at      = db.Column(db.DateTime)
    rejected_at      = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    created_by       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_by      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rejected_by      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    creator    = db.relationship("User", foreign_keys=[created_by], lazy="joined")
    approver   = db.relationship("User", foreign_keys=[approved_by], lazy="joined")
    rejecter   = db.relationship("User", foreign_keys=[rejected_by], lazy="joined")

    items      = db.relationship("QuoteItem",      backref="quote", lazy="select",
                                  cascade="all, delete-orphan", order_by="QuoteItem.sort_order")
    inclusions = db.relationship("QuoteInclusion", backref="quote", lazy="select",
                                  cascade="all, delete-orphan", order_by="QuoteInclusion.sort_order")

    def recalculate_total(self):
        self.total_amount = sum(i.total_price or 0 for i in self.items)

    @property
    def status_label(self) -> str:
        labels = {
            "pendente":           "Pendente",
            "aprovado":           "Aprovado",
            "reprovado":          "Reprovado",
            "pago":               "Pago",
            "reserva_confirmada": "Reserva Confirmada",
            "cancelado":          "Cancelado",
            "excluido":           "Exclu\u00eddo",
        }
        return labels.get(self.status, self.status)

    @property
    def status_color(self) -> str:
        colors = {
            "pendente":           "amber",
            "aprovado":           "green",
            "reprovado":          "red",
            "pago":               "emerald",
            "reserva_confirmada": "blue",
            "cancelado":          "slate",
            "excluido":           "slate",
        }
        return colors.get(self.status, "slate")

    def __repr__(self):
        return f"<Quote {self.number}>"


class QuoteItem(db.Model, TimestampMixin):
    __tablename__ = "quote_items"

    id                  = db.Column(db.Integer, primary_key=True)
    quote_id            = db.Column(db.Integer, db.ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False)
    service_id          = db.Column(db.Integer, db.ForeignKey("services.id"),           nullable=True)
    category_id         = db.Column(db.Integer, db.ForeignKey("vehicle_categories.id"), nullable=True)
    description         = db.Column(db.String(500))
    vehicle_description = db.Column(db.String(200))
    quantity            = db.Column(db.Integer, default=1)
    unit_price          = db.Column(db.Float, default=0)
    hour_extra          = db.Column(db.Float, default=0)
    total_price         = db.Column(db.Float, default=0)
    sort_order          = db.Column(db.Integer, default=0)

    price_base      = db.Column(db.Float, default=0)
    price_nf        = db.Column(db.Float, default=0)
    price_cartao    = db.Column(db.Float, default=0)
    price_nf_cartao = db.Column(db.Float, default=0)

    driver_name = db.Column(db.String(200))
    state_code  = db.Column(db.String(10))
    ref_note    = db.Column(db.String(200))

    category = db.relationship("VehicleCategory", foreign_keys=[category_id], lazy="select")

    km_extra      = db.Column(db.Float, default=0.0)
    km_extra_rate = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f"<QuoteItem {self.description}>"


# ---------------------------------------------------------------------------
# Standard inclusions / add-ons that appear in the PDF
# ---------------------------------------------------------------------------
DEFAULT_INCLUSIONS = [
    # group: incluso
    {"text_pt": "Meet & Greet",                                            "text_en": "Meet & Greet",                                           "group": "incluso"},
    {"text_pt": "1 Hora de Espera após o pouso do vôo.",                   "text_en": "1 Hour of Wait after flight landing.",                    "group": "incluso"},
    {"text_pt": "Serviço de Bordo",                                        "text_en": "On-board Service",                                       "group": "incluso"},
    {"text_pt": "Pedágios e Combustível",                                  "text_en": "Tolls and Fuel",                                         "group": "incluso"},
    # group: info
    {"text_pt": "Hora Extra Adicional é cobrada a partir de 30 minutos.",  "text_en": "Additional Overtime is charged after 30 minutes.",       "group": "info"},
]


class QuoteInclusion(db.Model):
    __tablename__ = "quote_inclusions"

    id         = db.Column(db.Integer, primary_key=True)
    quote_id   = db.Column(db.Integer, db.ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False)
    text_pt    = db.Column(db.String(500), nullable=False)
    text_en    = db.Column(db.String(500), default="")
    included   = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"<QuoteInclusion {self.text_pt[:40]}>"
