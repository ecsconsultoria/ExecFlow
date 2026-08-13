import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @property
    def SQLALCHEMY_ENGINE_OPTIONS(self):
        """Engine options dependem do driver.

        SQLite (dev/OneDrive): timeout + check_same_thread evitam "database is locked".
        Postgres (prod/Render): não aceita esses connect_args — só pool tuning.
        """
        url = os.environ.get("DATABASE_URL", "")
        opts = {"pool_pre_ping": True, "pool_recycle": 300}
        if url.startswith("sqlite") or not url:
            opts["connect_args"] = {"timeout": 30, "check_same_thread": False}
        return opts

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

    # Company public contact (usado no rodapé dos recibos)
    COMPANY_WEBSITE = os.environ.get("COMPANY_WEBSITE", "www.executivecarsp.com")
    COMPANY_PHONE   = os.environ.get("COMPANY_PHONE", "+55 11 2371-1500")

    # App
    BASE_URL       = os.environ.get("BASE_URL", "http://localhost:5004")
    ORCAMENTOS_DIR = os.environ.get("ORCAMENTOS_DIR", "orcamentos")
    WPP_NUMBER     = os.environ.get("WPP_NUMBER", "5511989178312")
    # Persistent upload folder (set UPLOAD_FOLDER=/orcamentos/uploads on Render)
    UPLOAD_FOLDER  = os.environ.get("UPLOAD_FOLDER", "")

    # Tax rates
    NF_RATE   = float(os.environ.get("NF_RATE", "0.10"))
    CARD_RATE = float(os.environ.get("CARD_RATE", "0.065"))

    # ── Session cookie hardening (Phase 8) ─────────────────────────
    # HttpOnly: bloqueia leitura via document.cookie (defesa XSS → roubo de sessão)
    # SameSite=Lax: navegador NÃO envia cookie em POSTs cross-site → defesa CSRF
    # Secure: cookie só trafega em HTTPS (ativado em produção via env ou ProductionConfig)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE   = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    # Sessão expira em 8h de inatividade (default; sobrescrevível via env)
    PERMANENT_SESSION_LIFETIME = int(os.environ.get("SESSION_LIFETIME_SECONDS", 28800))
    # ── CSRF (Flask-WTF) ────────────────────────────────────
    # Token de sessão exigido em todo POST/PUT/PATCH/DELETE.
    # Templates injetam {{ csrf_token() }} nos forms; AJAX usa header X-CSRFToken.
    WTF_CSRF_ENABLED   = True
    WTF_CSRF_TIME_LIMIT = int(os.environ.get("WTF_CSRF_TIME_LIMIT", 28800))
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        url = os.environ.get("DATABASE_URL", "sqlite:///DB_V2.db")
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    # Em produção exigir HTTPS no cookie de sessão (sobrescreve env var ausente)
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # Desabilita CSRF durante testes (test_client não emite tokens).
    WTF_CSRF_ENABLED = False


config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
    "default":     DevelopmentConfig,
}
