"""checkin_service.py — Check-in do motorista pelo link público da agenda.

Fluxo progressivo de status:
  INICIAL           → [Aceitar]
  aceito            → [A Caminho do Cliente] [Aguardando Cliente]
  a_caminho_cliente → [Aceitar] [Aguardando Cliente] [Cliente Embarcou]
  aguardando_cliente→ [Aceitar] [Cliente Embarcou] [No Show]
  cliente_embarcou  → [Aceitar] [Finalizado]
  finalizado        → somente [Reverter] (volta um passo)
  no_show           → [Aceitar] (recomeçar)
"""
from __future__ import annotations

from ..extensions import db
from ..utils import now_br

CHECKIN_STATUSES = [
    "aceito",
    "a_caminho_cliente",
    "aguardando_cliente",
    "cliente_embarcou",
    "finalizado",
    "no_show",
]

CHECKIN_LABELS = {
    "pt": {
        "aceito": "Aceita",
        "a_caminho_cliente": "A Caminho do Cliente",
        "aguardando_cliente": "Aguardando Cliente",
        "cliente_embarcou": "Cliente Embarcou",
        "finalizado": "Finalizado",
        "no_show": "No Show",
    },
    "en": {
        "aceito": "Accept",
        "a_caminho_cliente": "En route to Pickup",
        "aguardando_cliente": "At Pickup",
        "cliente_embarcou": "Pax on Board",
        "finalizado": "Finished",
        "no_show": "No Show",
    },
}


def visible_statuses(current: str | None) -> list[str]:
    """Botões visíveis para o status atual (fluxo progressivo LINEAR).

    Cada etapa mostra apenas o(s) próximo(s) passo(s) — sem botão de voltar
    no meio do fluxo (o Reverter só existe em Finalizado).
    """
    current = current or ""
    if not current:
        return ["aceito"]
    if current == "aceito":
        return ["a_caminho_cliente", "aguardando_cliente"]
    if current == "a_caminho_cliente":
        return ["aguardando_cliente", "cliente_embarcou"]
    if current == "aguardando_cliente":
        return ["cliente_embarcou", "no_show"]
    if current == "cliente_embarcou":
        return ["finalizado"]
    if current == "no_show":
        return []  # somente o Reverter (igual ao finalizado)
    # finalizado (ou desconhecido): nenhum botão — só o Reverter
    return []


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
