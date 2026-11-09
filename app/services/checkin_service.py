"""checkin_service.py — Check-in do motorista pelo link público da agenda.

Fluxo de status: A CAMINHO DO CLIENTE → AGUARDANDO CLIENTE →
CLIENTE EMBARCADO → A CAMINHO DESTINO → FINALIZADO. "Finalizado" marca o
op_completed_at do item (integra com a regra de conclusão do pedido).
Revert volta um passo (status anterior).
"""
from __future__ import annotations

from ..extensions import db
from ..utils import now_br

CHECKIN_STATUSES = [
    "a_caminho_cliente",
    "aguardando_cliente",
    "cliente_embarcado",
    "a_caminho_destino",
    "finalizado",
]

CHECKIN_LABELS = {
    "pt": {
        "a_caminho_cliente": "A Caminho do Cliente",
        "aguardando_cliente": "Aguardando Cliente",
        "cliente_embarcado": "Cliente Embarcado",
        "a_caminho_destino": "A Caminho do Destino",
        "finalizado": "Finalizado",
    },
    "en": {
        "a_caminho_cliente": "En Route to Client",
        "aguardando_cliente": "Waiting for Client",
        "cliente_embarcado": "Client On Board",
        "a_caminho_destino": "En Route to Destination",
        "finalizado": "Completed",
    },
}


def apply_status(item, status: str) -> None:
    """Aplica um novo status do motorista (guarda o anterior p/ revert).

    Vale para OrderItem (SO) e POItem (PO). "Finalizado" marca o
    op_completed_at do item; no SO, integra com a regra de conclusão do pedido.
    """
    if status not in CHECKIN_STATUSES:
        raise ValueError("Status inválido")
    if getattr(item, "op_driver_status", None) == status:
        return
    item.op_driver_status_prev = getattr(item, "op_driver_status", None)
    item.op_driver_status      = status
    item.op_driver_status_at   = now_br()
    if status == "finalizado" and not getattr(item, "op_completed_at", None):
        item.op_completed_at = now_br()
        # SO: conclui o pedido pela regra (faturado + todas pagas + agenda concluída)
        if hasattr(item, "order"):
            from .order_service import _should_complete
            if _should_complete(item.order):
                item.order.status    = "concluido"
                item.order.closed_at = now_br()
    db.session.commit()


def revert_status(item) -> None:
    """Volta ao status anterior (um passo)."""
    if not getattr(item, "op_driver_status_prev", None):
        return
    item.op_driver_status      = item.op_driver_status_prev
    item.op_driver_status_prev = None
    item.op_driver_status_at   = now_br()
    db.session.commit()
