from ..extensions import db
from .base import TimestampMixin


class AuditLog(db.Model, TimestampMixin):
    __tablename__ = "audit_logs"

    id         = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"),     nullable=True)
    entity     = db.Column(db.String(100))
    entity_id  = db.Column(db.Integer)
    action     = db.Column(db.String(100))   # create, update, delete, login, etc.
    old_data   = db.Column(db.JSON)
    new_data   = db.Column(db.JSON)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))

    def __repr__(self):
        return f"<AuditLog {self.entity}:{self.entity_id} {self.action}>"
