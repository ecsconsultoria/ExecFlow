"""ServiceOrderEvent — timeline operacional da OS.

Todo evento relevante (atribuição, envio de dados, mudança de status, nota manual)
é registrado aqui com timestamp, usuário e metadados opcionais (JSON).
"""
from ..extensions import db
from .base import TimestampMixin

EVENT_TYPES = (
    "criado",
    "aprovado",
    "pago",
    "faturado",
    "agendado",
    "motorista_atribuido",
    "fornecedor_atribuido",
    "dados_enviados_cliente",
    "iniciado",
    "finalizado",
    "cancelado",
    "nota",
    "custo_adicionado",
    "status_alterado",
)

EVENT_ICONS = {
    "criado":                "fa-plus-circle",
    "aprovado":              "fa-circle-check",
    "pago":                  "fa-money-bill-wave",
    "faturado":              "fa-file-invoice",
    "agendado":              "fa-calendar-check",
    "motorista_atribuido":   "fa-id-card",
    "fornecedor_atribuido":  "fa-handshake",
    "dados_enviados_cliente":"fa-paper-plane",
    "iniciado":              "fa-play-circle",
    "finalizado":            "fa-flag-checkered",
    "cancelado":             "fa-ban",
    "nota":                  "fa-sticky-note",
    "custo_adicionado":      "fa-coins",
    "status_alterado":       "fa-arrows-rotate",
}

EVENT_COLORS = {
    "criado":                "slate",
    "aprovado":              "green",
    "pago":                  "emerald",
    "faturado":              "teal",
    "agendado":              "blue",
    "motorista_atribuido":   "violet",
    "fornecedor_atribuido":  "purple",
    "dados_enviados_cliente":"cyan",
    "iniciado":              "amber",
    "finalizado":            "green",
    "cancelado":             "red",
    "nota":                  "slate",
    "custo_adicionado":      "orange",
    "status_alterado":       "blue",
}


class ServiceOrderEvent(db.Model, TimestampMixin):
    __tablename__ = "service_order_events"

    id               = db.Column(db.Integer, primary_key=True)
    service_order_id = db.Column(db.Integer, db.ForeignKey("service_orders.id"), nullable=False)
    user_id          = db.Column(db.Integer, db.ForeignKey("users.id"),          nullable=True)
    event_type       = db.Column(db.String(50), nullable=False)
    description      = db.Column(db.Text)
    event_metadata   = db.Column("metadata", db.JSON)

    user = db.relationship("User", foreign_keys=[user_id], lazy="joined")

    @property
    def icon(self):
        return EVENT_ICONS.get(self.event_type, "fa-circle")

    @property
    def color(self):
        return EVENT_COLORS.get(self.event_type, "slate")

    def __repr__(self):
        return f"<ServiceOrderEvent {self.event_type} os={self.service_order_id}>"
