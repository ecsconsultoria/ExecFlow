"""cash_flow_service.py — Fluxo de Caixa REALIZADO (Etapa 4).

FONTE OFICIAL DOS MOVIMENTOS: FinancialRecord (ledger único).

Regras:
  * ENTRADA = FinancialRecord type='revenue', status='pago', paid_date no período.
    (Receita reconhecida ≠ recebimento: SO faturado sem baixa NÃO entra.)
  * SAÍDA  = FinancialRecord type='cost'   (PO)  ou type='expense' (Despesa Geral),
    status='pago', paid_date no período.
    (PO/despesa pendentes, vencidas ou canceladas NÃO entram; rascunho não gera FR.)
  * Cada movimento aparece EXATAMENTE UMA VEZ — o FR é o espelho 1:1 do
    pagamento (reference única + índice parcial UNIQUE). Não existe tabela
    paralela de movimentos; nenhuma duplicação possível entre parcela e FR.

A data do movimento é paid_date (data real do recebimento/pagamento) — nunca
created_at nem emission_date.
"""
from ..models.financial import FinancialRecord


def realized_entries(cid, start, end):
    """Todos os movimentos realizados (entradas + saídas) do período."""
    return (FinancialRecord.query
            .filter_by(company_id=cid)
            .filter(FinancialRecord.deleted_at.is_(None))
            .filter(FinancialRecord.status == "pago")
            .filter(FinancialRecord.paid_date.isnot(None))
            .filter(FinancialRecord.paid_date.between(start, end))
            .order_by(FinancialRecord.paid_date.asc(), FinancialRecord.id.asc())
            .all())


def split_movements(entries):
    """Separa em (inflows, outflows)."""
    inflows  = [e for e in entries if e.type == "revenue"]
    outflows = [e for e in entries if e.type in ("cost", "expense")]
    return inflows, outflows


def movement_info(entry) -> dict:
    """Resolve origem, partes relacionadas, categoria e centro de custo.

    Sempre a partir do ledger e dos vínculos opcionais — não reescreve nada.
    """
    ref = entry.reference or ""
    if ref.startswith("order_payment:"):
        origem = "SO"
        so_number, client_name = _resolve_order(ref)
        po_number = None
        supplier_name = None
    elif ref.startswith("po_payment:"):
        origem = "PO"
        po_number, supplier_name = _resolve_po(ref)
        so_number, client_name = None, None
    elif ref.startswith("expense:"):
        origem = "DESPESA"
        so_number, po_number = None, None
        supplier_name = entry.supplier.name if entry.supplier else None
        client_name = None
    else:
        origem = "OUTRA"
        so_number = po_number = None
        supplier_name = entry.supplier.name if entry.supplier else None
        client_name = None

    cat = entry.category_ref
    if cat is not None:
        root = cat.parent if cat.parent else cat
        category_label = cat.name
        group = root.name
    else:
        category_label = (entry.category or "") or "—"
        group = {
            "custo_fornecedor": "Custos Diretos",
            "custo_motorista": "Custos Diretos",
            "custo_operacional": "Despesas Operacionais",
            "imposto": "Impostos",
            "receita_servico": "Receitas",
        }.get(entry.category, "Outros")

    if so_number is None and entry.order is not None:
        so_number = entry.order.number
    if po_number is None and entry.purchase_order is not None:
        po_number = entry.purchase_order.number

    return {
        "origem": origem,
        "so_number": so_number,
        "po_number": po_number,
        "client_name": client_name,
        "supplier_name": supplier_name,
        "category_label": category_label,
        "cost_center": entry.cost_center.name if entry.cost_center else None,
        "group": group,
    }


def _resolve_order(ref):
    from ..models.order import OrderPayment, Order
    try:
        pid = int(ref.split(":", 1)[1])
    except (ValueError, IndexError):
        return None, None
    op = OrderPayment.query.get(pid)
    if op is None or op.order is None:
        return None, None
    o = op.order
    return o.number, (o.client_name or "")


def _resolve_po(ref):
    from ..models.purchase_order import POPayment, PurchaseOrder
    try:
        pid = int(ref.split(":", 1)[1])
    except (ValueError, IndexError):
        return None, None
    pp = POPayment.query.get(pid)
    if pp is None or pp.purchase_order is None:
        return None, None
    po = pp.purchase_order
    return po.number, (po.supplier.name if po.supplier else "")


def pending_forecast(cid):
    """Resumo PREVISTO (não realizado) para exibição informativa.

    A receber: FRs de receita pendentes. A pagar: FRs de custo (PO) e
    despesas pendentes. Nunca misturado com o caixa realizado.
    """
    from ..extensions import db
    from sqlalchemy import func

    def _sum(*cond):
        return (db.session.query(func.sum(FinancialRecord.amount))
                .filter(FinancialRecord.company_id == cid,
                        FinancialRecord.deleted_at.is_(None),
                        FinancialRecord.status == "pendente",
                        *cond)
                .scalar() or 0.0)

    to_receive = _sum(FinancialRecord.type == "revenue")
    to_pay = _sum(FinancialRecord.type.in_(["cost", "expense"]))
    return to_receive, to_pay


# ─────────────────────────────────────────────────────────────────────────────
# Etapa 9B — Saldo inicial (companies.settings) + Caixa Previsto (ar_ap_service)
# ─────────────────────────────────────────────────────────────────────────────

_SETTINGS_BALANCE = "cash_initial_balance"
_SETTINGS_BALANCE_DATE = "cash_initial_balance_date"


def initial_balance(company) -> tuple:
    """(valor, data) do saldo inicial configurado — NUNCA inferido.

    Lê companies.settings (JSON); sem configuração retorna (0.0, None).
    """
    settings = getattr(company, "settings", None) or {}
    value = settings.get(_SETTINGS_BALANCE)
    date_str = settings.get(_SETTINGS_BALANCE_DATE)
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    from datetime import date as _date
    try:
        ref_date = _date.fromisoformat(date_str) if date_str else None
    except (TypeError, ValueError):
        ref_date = None
    return value, ref_date


def set_initial_balance(company, value: float, ref_date, user_id: int) -> None:
    """Grava saldo inicial no JSON settings (única escrita desta etapa).

    Não faz commit — o chamador controla a transação. Auditoria fica no caller.
    """
    settings = dict(getattr(company, "settings", None) or {})
    settings[_SETTINGS_BALANCE] = round(float(value), 2)
    settings[_SETTINGS_BALANCE_DATE] = ref_date.isoformat() if ref_date else None
    company.settings = settings


def forecast_entries(cid, start, end):
    """(entradas_previstas, saídas_previstas) por DUE_DATE no período.

    Fonte única: ar_ap_service (AR/AP da Etapa 8B) — nenhuma regra paralela.
    Entradas = parcelas de SO a receber; Saídas = POPayment a pagar +
    despesas gerais pendentes. Nunca inclui pagos/cancelados.
    """
    from .ar_ap_service import receivable_rows, payable_rows
    return receivable_rows(cid, start, end), payable_rows(cid, start, end)
