from datetime import datetime
from ..extensions import db
from ..utils import now_br


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=now_br, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_br, onupdate=now_br, nullable=False)


class SoftDeleteMixin:
    deleted_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = now_br()
