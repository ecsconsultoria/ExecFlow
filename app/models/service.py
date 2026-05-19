from ..extensions import db
from .base import TimestampMixin


class State(db.Model, TimestampMixin):
    __tablename__ = "states"

    id   = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

    services = db.relationship("Service", backref="state", lazy="dynamic")

    def __repr__(self):
        return f"<State {self.code}>"


class Service(db.Model, TimestampMixin):
    __tablename__ = "services"

    id             = db.Column(db.Integer, primary_key=True)
    company_id     = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    state_id       = db.Column(db.Integer, db.ForeignKey("states.id"), nullable=False)
    name           = db.Column(db.String(200), nullable=False)
    description    = db.Column(db.Text)
    duration_hours = db.Column(db.Float)
    km_included    = db.Column(db.Float)
    is_active      = db.Column(db.Boolean, default=True)

    pricing     = db.relationship("ServicePricing", backref="service",
                                  lazy="dynamic", cascade="all, delete-orphan")
    quote_items = db.relationship("QuoteItem", backref="service", lazy="dynamic")

    def __repr__(self):
        return f"<Service {self.name}>"


class ServicePricing(db.Model, TimestampMixin):
    __tablename__ = "service_pricing"

    id              = db.Column(db.Integer, primary_key=True)
    service_id      = db.Column(db.Integer, db.ForeignKey("services.id"),            nullable=False)
    category_id     = db.Column(db.Integer, db.ForeignKey("vehicle_categories.id"),  nullable=False)
    driver_type     = db.Column(db.String(50), default="")
    price_cost      = db.Column(db.Float, default=0)
    price_base      = db.Column(db.Float, default=0)
    price_nf        = db.Column(db.Float, default=0)
    price_cartao    = db.Column(db.Float, default=0)
    price_nf_cartao = db.Column(db.Float, default=0)
    is_active       = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.UniqueConstraint("service_id", "category_id", "driver_type",
                            name="uq_service_category_driver"),
    )

    def effective_price(self, billing_type: str, nf_rate: float = 0.10, card_rate: float = 0.065) -> float:
        base = self.price_base or 0
        if billing_type == "nf":
            return self.price_nf if self.price_nf > 0 else round(base * (1 + nf_rate), 2)
        if billing_type == "cartao":
            return self.price_cartao if self.price_cartao > 0 else round(base * (1 + card_rate), 2)
        if billing_type == "nf_cartao":
            return self.price_nf_cartao if self.price_nf_cartao > 0 else round(base * (1 + nf_rate + card_rate), 2)
        return base

    def __repr__(self):
        return f"<ServicePricing svc={self.service_id} cat={self.category_id}>"
