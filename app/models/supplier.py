from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class Supplier(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "suppliers"

    id            = db.Column(db.Integer, primary_key=True)
    company_id    = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name          = db.Column(db.String(200), nullable=False)
    contact       = db.Column(db.String(200))
    email         = db.Column(db.String(200))
    phone         = db.Column(db.String(50))
    document      = db.Column(db.String(50))
    address       = db.Column(db.Text)
    city          = db.Column(db.String(100))
    state         = db.Column(db.String(10))
    service_type  = db.Column(db.String(200))
    payment_terms = db.Column(db.String(200))
    notes         = db.Column(db.Text)
    is_active     = db.Column(db.Boolean, default=True)

    drivers        = db.relationship("Driver",         backref="supplier",  lazy="dynamic")
    bookings       = db.relationship("Booking",        backref="supplier",  lazy="dynamic")
    service_orders = db.relationship("ServiceOrder",   backref="supplier",  lazy="dynamic",
                                     foreign_keys="ServiceOrder.supplier_id")

    def __repr__(self):
        return f"<Supplier {self.name}>"
