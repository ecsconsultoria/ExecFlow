"""margin_service.py — Cálculo financeiro central (SO↔PO).

FONTE ÚNICA de verdade (Etapa 2) para:
  * receita de serviço reconhecida (regra de faturamento);
  * custo direto válido (POs vinculadas ao SO, excluindo rascunho/cancelado/excluído);
  * margem bruta (R$ e %).

Dashboard e detalhes de SO devem ler daqui — nada de recalcular em telas.
Campos denormalizados (orders.total_po_cost / margin_amount) continuam existindo
como histórico, mas NÃO são reescritos por esta etapa e não alimentam os indicadores.
"""
from datetime import date as _date

from ..models.purchase_order import PO_INVALID_COST_STATUSES

# Status de SO cujo faturamento efetivo (invoiced_at) qualifica a receita.
# "concluido" entra somente quando a ordem foi de fato faturada antes de fechar;
# SO concluído sem faturamento NÃO é receita reconhecida (regra da Etapa 2).
_RECOGNIZED_STATUSES = frozenset({"faturado", "concluido"})


# ─────────────────────────────────────────────────────────────────────────────
# Receita reconhecida (regra única)
# ─────────────────────────────────────────────────────────────────────────────

def recognized_service_revenue(order) -> float:
    """Receita reconhecida de um SO.

    Regra: somente SO efetivamente faturado (invoiced_at preenchido) e que
    não tenha sido cancelado/excluído. SO novo/aberto/concluído-sem-fatura
    retornam 0 (não é receita).
    """
    if getattr(order, "status", None) not in _RECOGNIZED_STATUSES:
        return 0.0
    if getattr(order, "invoiced_at", None) is None:
        return 0.0
    return round(float(order.computed_total or 0.0), 2)


def invoice_date(order):
    """Data de competência da receita reconhecida (data do faturamento)."""
    ia = getattr(order, "invoiced_at", None)
    if ia is None:
        return None
    return ia.date() if hasattr(ia, "date") else ia


# ─────────────────────────────────────────────────────────────────────────────
# Custo direto válido (regra única)
# ─────────────────────────────────────────────────────────────────────────────

def direct_costs_for_order(order) -> list:
    """POs que representam custo direto realizado do SO.

    Regra: somente POs vinculadas ao SO (order_id) cujo status NÃO esteja em
    {rascunho, cancelado, excluido}. PO de outro SO ou sem SO não entra.
    """
    return [
        po for po in (getattr(order, "purchase_orders", None) or [])
        if (getattr(po, "status", None) or "") not in PO_INVALID_COST_STATUSES
    ]


def direct_cost_total(order) -> float:
    """Soma do custo direto válido do SO."""
    return round(sum(float(po.computed_total or 0.0) for po in direct_costs_for_order(order)), 2)


# ─────────────────────────────────────────────────────────────────────────────
# Margem bruta (regra única)
# ─────────────────────────────────────────────────────────────────────────────

def gross_margin(order) -> tuple:
    """Retorna (revenue, cost, margin) — receita reconhecida − custo direto."""
    revenue = recognized_service_revenue(order)
    cost = direct_cost_total(order)
    return revenue, cost, round(revenue - cost, 2)


def gross_margin_pct(order) -> float:
    """Margem % sobre a receita reconhecida (0 quando não há receita)."""
    revenue = recognized_service_revenue(order)
    if revenue <= 0:
        return 0.0
    margin = revenue - direct_cost_total(order)
    return round(margin / revenue * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Compatibilidade com o fluxo legado de denormalização
# (orders.total_po_cost / margin_amount) — mesmo custo, receita total do SO.
# ─────────────────────────────────────────────────────────────────────────────

def calculate_order_margin(order):
    """Return (revenue, cost, margin) floats para gravação denormalizada.

    Receita = computed_total do SO (valor comercial); custo = custo direto
    válido (mesma regra única — rascunho/cancelado/excluído fora).
    """
    revenue = float(order.computed_total or 0.0)
    cost = direct_cost_total(order)
    margin = revenue - cost
    return round(revenue, 2), round(cost, 2), round(margin, 2)


def recalculate_order(order):
    """Atualiza os campos denormalizados de margem e flush (sem commit).

    Chamado apenas por eventos naturais (faturar/baixa/concluir) — não é
    backfill: nenhum dado histórico é reescrito em lote.
    """
    from ..extensions import db  # local import avoids circular imports

    if getattr(order, 'status', None) == 'cancelado':
        order.margin_amount = 0.0
        order.total_po_cost = 0.0
        db.session.flush()
        return

    _revenue, cost, margin = calculate_order_margin(order)
    order.total_po_cost = cost
    order.margin_amount = margin
    db.session.flush()
