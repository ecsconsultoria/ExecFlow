from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class Driver(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "drivers"

    id             = db.Column(db.Integer, primary_key=True)
    company_id     = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    supplier_id    = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    name           = db.Column(db.String(200), nullable=False)
    phone          = db.Column(db.String(50))
    email          = db.Column(db.String(200))
    license_number = db.Column(db.String(50))
    license_expiry = db.Column(db.Date)
    language       = db.Column(db.String(50), default="monolingual")
    state          = db.Column(db.String(10))
    status         = db.Column(db.String(50), default="available")
    notes          = db.Column(db.Text)
    is_active      = db.Column(db.Boolean, default=True)

    @property
    def language_label(self):
        return "Motorista Bilíngue" if self.language == "bilingual" else "Motorista Monolíngue"

    def __repr__(self):
        return f"<Driver {self.name}>"
