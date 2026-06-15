from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin

CATEGORY_TYPES = ('transport', 'vehicle', 'logistics', 'expense', 'financial_expense', 'supplier_service')

CATEGORIES = [
    "Motorista Free Lance",
    "Sedan Executivo",
    "Sedan Premium",
    "SUV Executivo",
    "SUV Executivo Premium",
    "Minivan Executivo",
    "Minivan Executivo Premium",
    "Van Executiva",
    "Sedan Blindado",
    "Sedan Blindado Premium",
    "SUV Blindado",
    "SUV Blindado Premium",
    "Minivan Blindado",
    "Minivan Blindado Premium",
    "Van Blindada",
    "Microônibus Executivo",
    "Ônibus Executivo",
]


class VehicleCategory(db.Model, TimestampMixin):
    __tablename__ = "vehicle_categories"

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(200), nullable=False, unique=True)
    slug          = db.Column(db.String(200), unique=True)
    description   = db.Column(db.Text)
    sort_order    = db.Column(db.Integer, default=0)
    is_active     = db.Column(db.Boolean, default=True)
    km_extra_rate = db.Column(db.Float, default=0.0)
    category_type = db.Column(db.String(50), nullable=False, default='transport')

    vehicles        = db.relationship("Vehicle",        backref="category", lazy="dynamic")
    service_pricing = db.relationship("ServicePricing", backref="category", lazy="dynamic")

    def __repr__(self):
        return f"<VehicleCategory {self.name}>"


class Vehicle(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "vehicles"

    id          = db.Column(db.Integer, primary_key=True)
    company_id  = db.Column(db.Integer, db.ForeignKey("companies.id"),         nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("vehicle_categories.id"), nullable=False)
    make        = db.Column(db.String(100))
    model       = db.Column(db.String(100))
    year        = db.Column(db.Integer)
    plate       = db.Column(db.String(20))
    color       = db.Column(db.String(50))
    capacity    = db.Column(db.Integer)
    status      = db.Column(db.String(50), default="available")
    notes       = db.Column(db.Text)
    is_active   = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Vehicle {self.plate}>"
