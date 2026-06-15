from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class Client(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "clients"

    id         = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name       = db.Column(db.String(200), nullable=False)
    contact    = db.Column(db.String(200))
    email      = db.Column(db.String(200))
    phone      = db.Column(db.String(50))
    whatsapp   = db.Column(db.String(50))
    document   = db.Column(db.String(50))   # CPF/CNPJ
    address    = db.Column(db.Text)
    city       = db.Column(db.String(100))
    state      = db.Column(db.String(10))
    country    = db.Column(db.String(100), default="Brasil")
    language       = db.Column(db.String(10), default="pt")
    billing_type   = db.Column(db.String(50), default="recibo")
    payment_method = db.Column(db.String(50))
    notes          = db.Column(db.Text)
    is_active      = db.Column(db.Boolean, default=True)

    quotes   = db.relationship("Quote",        backref="client", lazy="dynamic")
    service_orders = db.relationship("ServiceOrder", backref="client", lazy="dynamic")

    def __repr__(self):
        return f"<Client {self.name}>"
