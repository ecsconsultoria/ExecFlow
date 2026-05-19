from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin

BOOKING_STATUSES = ("confirmado", "em_andamento", "concluido", "cancelado")


class Booking(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "bookings"

    id          = db.Column(db.Integer, primary_key=True)
    company_id  = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    quote_id    = db.Column(db.Integer, db.ForeignKey("quotes.id"),    nullable=True)
    client_id   = db.Column(db.Integer, db.ForeignKey("clients.id"),   nullable=True)
    number      = db.Column(db.String(50), unique=True)
    status      = db.Column(db.String(50), default="confirmado")

    service_date     = db.Column(db.DateTime)
    pickup_address   = db.Column(db.Text)
    dropoff_address  = db.Column(db.Text)
    flight_number    = db.Column(db.String(50))
    pax_count        = db.Column(db.Integer, default=1)

    driver_id   = db.Column(db.Integer, db.ForeignKey("drivers.id"),   nullable=True)
    vehicle_id  = db.Column(db.Integer, db.ForeignKey("vehicles.id"),  nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)

    notes        = db.Column(db.Text)
    driver_notes = db.Column(db.Text)

    driver_info_sent    = db.Column(db.Boolean, default=False)
    driver_info_sent_at = db.Column(db.DateTime)

    confirmed_at  = db.Column(db.DateTime)
    completed_at  = db.Column(db.DateTime)

    financial_records = db.relationship("FinancialRecord", backref="booking", lazy="dynamic")
    service_order     = db.relationship("ServiceOrder",    backref="booking", uselist=False)

    def __repr__(self):
        return f"<Booking {self.number}>"
