import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}

    # E-mail
    SMTP_HOST    = os.environ.get("SMTP_HOST", "")
    SMTP_PORT    = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER    = os.environ.get("SMTP_USER", "")
    SMTP_PASS    = os.environ.get("SMTP_PASS", "")
    SENDER_NAME  = os.environ.get("SENDER_NAME", "Executive Car SP")
    EMAIL_ADMIN  = os.environ.get("EMAIL_ADMIN", "")

    # PayPal
    PAYPAL_CLIENT_ID     = os.environ.get("PAYPAL_CLIENT_ID", "")
    PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
    PAYPAL_MODE          = os.environ.get("PAYPAL_MODE", "sandbox")

    # PIX static key
    PIX_KEY           = os.environ.get("PIX_KEY", "")
    PIX_MERCHANT_NAME = os.environ.get("PIX_MERCHANT_NAME", "Executive Car SP")
    PIX_MERCHANT_CITY = os.environ.get("PIX_MERCHANT_CITY", "Sao Paulo")

    # App
    BASE_URL       = os.environ.get("BASE_URL", "http://localhost:5004")
    ORCAMENTOS_DIR = os.environ.get("ORCAMENTOS_DIR", "orcamentos")
    WPP_NUMBER     = os.environ.get("WPP_NUMBER", "5511989178312")
    # Persistent upload folder (set UPLOAD_FOLDER=/orcamentos/uploads on Render)
    UPLOAD_FOLDER  = os.environ.get("UPLOAD_FOLDER", "")

    # Tax rates
    NF_RATE   = float(os.environ.get("NF_RATE", "0.10"))
    CARD_RATE = float(os.environ.get("CARD_RATE", "0.065"))

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        url = os.environ.get("DATABASE_URL", "sqlite:///erp_v4.db")
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
    "default":     DevelopmentConfig,
}
