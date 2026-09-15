"""dre_service.py — DRE Gerencial por COMPETÊNCIA (Etapa 5).

FONTES (nenhum dado é alterado; tudo calculado em tempo de consulta):
  * Receita   = Orders faturadas (competência = invoiced_at) OU concluídas
                sem faturamento (competência = closed_at).
  * Custos    = TODAS as POs válidas (fora rascunho/cancelado/excluído), com ou
                sem SO vinculado (regra do usuário 15/09/2026 — custo é tudo que
                saiu). Competência (prioridade):
                  1. service_date dos itens da PO (data real de execução);
                  2. delivery_date da PO (data operacional);
                  3. somente se não houver informação melhor: created_at.
  * Despesas  = FinancialRecord type='expense' não cancelada,
                competência = emission_date (obrigatória na Etapa 3B).
                Agrupadas pela categoria-raiz do catálogo 3A.

DRE ≠ Caixa: pendente entra na DRE por competência; caixa só no pagamento.
Nenhuma tabela nova, nenhuma migration, nenhum backfill.
"""
from datetime import date as _date

from ..models.order import Order
from ..models.purchase_order import PurchaseOrder, PO_INVALID_COST_STATUSES
from ..models.financial import FinancialRecord

# Grupos da DRE na ordem de exibição (categoria-raiz do catálogo 3A)
DRE_EXPENSE_GROUPS = [
    "Despesas Operacionais",
    "Despesas Administrativas",
    "Pessoal",
    "Impostos",
    "Despesas Financeiras",
]


# ─────────────────────────────────────────────────────────────────────────────
# Receita (regra da Etapa 2 — competência = faturamento)
# ─────────────────────────────────────────────────────────────────────────────

def revenue_rows(cid, start, end):
    """SOs com receita reconhecida no período.

    Competência = data do faturamento (invoiced_at). SOs CONCLUÍDAS sem
    faturamento entram pela data de conclusão (closed_at) — ou, quando a
    conclusão foi automática (baixa das parcelas, sem closed_at gravado),
    pela data do último pagamento — o dinheiro entrou e o pedido foi
    encerrado, então a receita não pode sumir da DRE.
    """
    rows = (Order.query
            .filter_by(company_id=cid, deleted_at=None)
            .filter(Order.status.in_(["faturado", "concluido"]))
            .filter(Order.invoiced_at.isnot(None))
            .filter(Order.invoiced_at >= _start_dt(start))
            .filter(Order.invoiced_at <= _end_dt(end))
            .all())
    for o in (Order.query
              .filter_by(company_id=cid, deleted_at=None)
              .filter(Order.status == "concluido")
              .filter(Order.invoiced_at.is_(None))
              .all()):
        comp = revenue_competence(o)
        if comp and start <= comp <= end:
            rows.append(o)
    rows.sort(key=lambda o: revenue_competence(o) or _date.min)
    return rows


def revenue_competence(o):
    """Data de competência da receita de uma SO: faturamento → conclusão →
    último pagamento."""
    if o.invoiced_at:
        return o.invoiced_at.date()
    if o.closed_at:
        return o.closed_at.date()
    paid = [p.paid_at for p in o.payments if getattr(p, "paid_at", None)]
    return max(paid).date() if paid else None


def recognized_revenue(cid, start, end) -> float:
    return round(sum(float(o.computed_total or 0) for o in revenue_rows(cid, start, end)), 2)


def other_revenue_rows(cid, start, end):
    """Receitas fora da venda de serviços (FR manuais) — RECEITA NÃO CLASSIFICADA.

    Competência = coalesce(emission_date, paid_date, created_at). Não altera nada.
    """
    rows = []
    for fr in (FinancialRecord.query
               .filter_by(company_id=cid, type="revenue")
               .filter(FinancialRecord.deleted_at.is_(None))
               .filter(FinancialRecord.status != "cancelado")
               .all()):
        ref = fr.reference or ""
        if ref.startswith("order_payment:"):
            continue
        d = fr.emission_date or fr.paid_date or (fr.created_at.date() if fr.created_at else None)
        if d and start <= d <= end:
            rows.append(fr)
    return rows


def other_revenue(cid, start, end) -> float:
    return round(sum(float(fr.amount or 0) for fr in other_revenue_rows(cid, start, end)), 2)


# ─────────────────────────────────────────────────────────────────────────────
# Custos diretos (competência com prioridade)
# ─────────────────────────────────────────────────────────────────────────────

def po_competence_date(po) -> _date:
    """Data de competência de uma PO.

    Prioridade: service_date dos itens → delivery_date → created_at.
    Nunca inventa data; se nada existir, retorna None (INDETERMINADA).
    """
    items = getattr(po, "items", None) or []
    service_dates = [i.service_date for i in items if getattr(i, "service_date", None)]
    if service_dates:
        return max(service_dates)
    if getattr(po, "delivery_date", None):
        return po.delivery_date
    if getattr(po, "created_at", None):
        return po.created_at.date()
    return None


def direct_cost_rows(cid, start, end):
    """POs de custo direto realizado no período (por competência).

    TODAS as POs válidas (fora rascunho/cancelado/excluído) entram, com ou
    sem SO vinculado — regra do usuário 15/09/2026 (custo é tudo que saiu).
    Retorna lista de (po, competência, usou_fallback).
    """
    pos = (PurchaseOrder.query
           .filter_by(company_id=cid)
           .filter(PurchaseOrder.deleted_at.is_(None))
           .filter(PurchaseOrder.status.notin_(list(PO_INVALID_COST_STATUSES)))
           .order_by(PurchaseOrder.id.asc())
           .all())
    rows = []
    for po in pos:
        comp = po_competence_date(po)
        if comp is None:
            continue  # competência indeterminada (pendência)
        if start <= comp <= end:
            fallback = not ([i.service_date for i in (po.items or [])
                             if getattr(i, "service_date", None)] or po.delivery_date)
            rows.append((po, comp, fallback))
    return rows


def direct_costs(cid, start, end) -> float:
    return round(sum(float(po.computed_total or 0) for po, _, _ in direct_cost_rows(cid, start, end)), 2)


def unclassified_cost_rows(cid):
    """(vazio) Todas as POs válidas agora entram no custo direto — a categoria
    'não classificado' deixou de existir (regra do usuário 15/09/2026).
    Mantida a assinatura para compatibilidade de tela/exportações.
    """
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Despesas gerais (competência = emissão; agrupadas por categoria-raiz)
# ─────────────────────────────────────────────────────────────────────────────

def expense_rows(cid, start, end):
    """Despesas (type='expense') não canceladas cuja emissão cai no período."""
    return (FinancialRecord.query
            .filter_by(company_id=cid, type="expense")
            .filter(FinancialRecord.deleted_at.is_(None))
            .filter(FinancialRecord.status != "cancelado")
            .filter(FinancialRecord.emission_date.isnot(None))
            .filter(FinancialRecord.emission_date.between(start, end))
            .order_by(FinancialRecord.emission_date.asc())
            .all())


def _expense_group(fr) -> str:
    cat = fr.category_ref
    if cat is None:
        return "Despesas Não Classificadas"
    root = cat.parent if cat.parent else cat
    return root.name


def general_expenses_by_group(cid, start, end) -> dict:
    groups = {g: 0.0 for g in DRE_EXPENSE_GROUPS}
    groups["Despesas Não Classificadas"] = 0.0
    for fr in expense_rows(cid, start, end):
        groups[_expense_group(fr)] = round(groups.get(_expense_group(fr), 0.0)
                                           + float(fr.amount or 0), 2)
    return groups


def general_expenses(cid, start, end) -> float:
    return round(sum(general_expenses_by_group(cid, start, end).values()), 2)


def indeterminate_expense_rows(cid):
    """COMPETÊNCIA INDETERMINADA: despesa sem emission_date (nunca entra na DRE)."""
    return (FinancialRecord.query
            .filter_by(company_id=cid, type="expense")
            .filter(FinancialRecord.deleted_at.is_(None))
            .filter(FinancialRecord.status != "cancelado")
            .filter(FinancialRecord.emission_date.is_(None))
            .all())


# ─────────────────────────────────────────────────────────────────────────────
# Resultado
# ─────────────────────────────────────────────────────────────────────────────

def gross_margin(cid, start, end) -> float:
    """Receita (serviços + outras) − custos diretos."""
    return round((recognized_revenue(cid, start, end) + other_revenue(cid, start, end))
                 - direct_costs(cid, start, end), 2)


def operating_result(cid, start, end) -> float:
    """Margem bruta − despesas gerais."""
    return round(gross_margin(cid, start, end) - general_expenses(cid, start, end), 2)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de período
# ─────────────────────────────────────────────────────────────────────────────

def _start_dt(d):
    from datetime import datetime
    return datetime.combine(d, datetime.min.time())


def _end_dt(d):
    from datetime import datetime
    return datetime.combine(d, datetime.max.time())
