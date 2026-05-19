from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db, login_manager
from .base import TimestampMixin


ROLES = ("superadmin", "admin", "manager", "operator")


class User(db.Model, UserMixin, TimestampMixin):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    company_id    = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name          = db.Column(db.String(200), nullable=False)
    email         = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(500))
    role          = db.Column(db.String(50), default="operator")
    is_active     = db.Column(db.Boolean, default=True)
    last_login    = db.Column(db.DateTime)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles) -> bool:
        return self.role in roles

    def __repr__(self):
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
