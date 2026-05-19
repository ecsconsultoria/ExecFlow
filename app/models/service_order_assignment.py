"""ServiceOrderAssignment — histórico completo de atribuições de uma OS.

Cada atribuição (motorista interno, fornecedor terceirizado, etc.) é registrada aqui.
Quando há uma nova atribuição, a anterior recebe is_current=False — nunca deletada.
Auditabilidade operacional crítica.
"""
from ..extensions import db
from .base import TimestampMixin

ASSIGNMENT_TYPES = ("internal", "outsourced")


class ServiceOrderAssignment(db.Model, TimestampMixin):
    __tablename__ = "service_order_assignments"

    id               = db.Column(db.Integer, primary_key=True)
    service_order_id = db.Column(db.Integer, db.ForeignKey("service_orders.id"), nullable=False)
    assigned_by      = db.Column(db.Integer, db.ForeignKey("users.id"),          nullable=True)
    assigned_at      = db.Column(db.DateTime, nullable=False)
    assignment_type  = db.Column(db.String(20), default="internal")  # internal | outsourced
    is_current       = db.Column(db.Boolean, default=True)

    # Internal assignment
    driver_id  = db.Column(db.Integer, db.ForeignKey("drivers.id"),  nullable=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True)

    # Outsourced assignment
    supplier_id          = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    supplier_driver_name = db.Column(db.String(200))
    supplier_vehicle     = db.Column(db.String(200))
    supplier_contact     = db.Column(db.String(200))
    supplier_price       = db.Column(db.Float, default=0.0)

    notes = db.Column(db.Text)

    driver   = db.relationship("Driver",   foreign_keys=[driver_id],   lazy="joined")
    vehicle  = db.relationship("Vehicle",  foreign_keys=[vehicle_id],  lazy="joined")
    supplier = db.relationship("Supplier", foreign_keys=[supplier_id], lazy="joined")

    def __repr__(self):
        return f"<ServiceOrderAssignment os={self.service_order_id} type={self.assignment_type} current={self.is_current}>"
