from ..extensions import db
from .base import TimestampMixin


class Company(db.Model, TimestampMixin):
    __tablename__ = "companies"

    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(200), nullable=False)
    slug     = db.Column(db.String(100), unique=True, nullable=False)
    email    = db.Column(db.String(200))
    phone    = db.Column(db.String(50))
    document = db.Column(db.String(50))   # CNPJ
    address  = db.Column(db.Text)
    logo_url = db.Column(db.String(500))
    plan     = db.Column(db.String(50), default="basic")    # basic, pro, enterprise
    status   = db.Column(db.String(50), default="active")   # active, suspended, cancelled
    settings = db.Column(db.JSON)

    # Relationships
    users          = db.relationship("User",          backref="company", lazy="dynamic")
    clients        = db.relationship("Client",        backref="company", lazy="dynamic")
    suppliers      = db.relationship("Supplier",      backref="company", lazy="dynamic")
    drivers        = db.relationship("Driver",        backref="company", lazy="dynamic")
    vehicles       = db.relationship("Vehicle",       backref="company", lazy="dynamic")
    quotes         = db.relationship("Quote",         backref="company", lazy="dynamic")
    service_orders = db.relationship("ServiceOrder",  backref="company", lazy="dynamic")

    def __repr__(self):
        return f"<Company {self.name}>"
