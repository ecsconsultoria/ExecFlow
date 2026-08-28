"""ar_ap_service.py — AR/AP UNIFICADOS (Etapa 8B).

FONTE ÚNICA das obrigações por empresa/período — Dashboard, Painel Financeiro
e telas de AR/AP consomem estas funções (nenhuma regra paralela em rotas).

Regras (Etapas 2–8A, preservadas):
  * AR = OrderPayment válida (SO não excluído/cancelado) NÃO recebida.
    Data da obrigação = due_date (NUNCA paid_date/invoiced_at).
  * AP = duas origens, sem duplicação:
      A) Custos de Serviços: POPayment válida (PO não excluída/cancelada)
         não paga;
      B) Despesas Gerais: FinancialRecord type='expense', status='pendente'
         (canceladas fora; pagas fora do saldo).
  * Vencido = não pago/recebido com due_date < hoje.
  * Recebido/Pago no período = FinancialRecord pago por paid_date (caixa).
  * Caixa e DRE: INALTERADOS (fontes próprias das Etapas 4 e 5).
"""
from datetime import date as _date

from ..models.order import Order, OrderPayment
from ..models.purchase_order import PurchaseOrder, POPayment
from ..models.financial import FinancialRecord


class ReceivableRow:
    """Obrigação de recebimento unificada para exibição."""

    def __init__(self, origem, description, due_date, amount, *, so_number=None,
                 client_name=None, payment=None):
        self.origem = origem          # "SO"
        self.description = description
        self.due_date = due_date
        self.amount = amount
        self.so_number = so_number
        self.client_name = client_name
        self.payment = payment        # OrderPayment original

    @property
    def is_overdue(self):
        return self.due_date is not None and self.due_date < _today()

    # Compatibilidade com o template do Dashboard (acessa a parcela original)
    @property
    def order_id(self):
        return self.payment.order_id if self.payment else None

    @property
    def order(self):
        return self.payment.order if self.payment else None


class PayableRow:
    """Obrigação de pagamento unificada para exibição."""

    def __init__(self, origem, description, due_date, amount, *, po_number=None,
                 supplier_name=None, expense=None, payment=None):
        self.origem = origem          # "PO" | "DESPESA"
        self.description = description
        self.due_date = due_date
        self.amount = amount
        self.po_number = po_number
        self.supplier_name = supplier_name
        self.expense = expense        # FinancialRecord de despesa (se origem DESPESA)
        self.payment = payment        # POPayment original (se origem PO)

    @property
    def is_overdue(self):
        return self.due_date is not None and self.due_date < _today()

    # Compatibilidade com o template do Dashboard (PO origem acessa purchase_order)
    @property
    def purchase_order(self):
        return self.payment.purchase_order if self.payment else None


def _today():
    from ..utils import now_br
    return now_br().date()


# ─────────────────────────────────────────────────────────────────────────────
# AR — Contas a Receber
# ─────────────────────────────────────────────────────────────────────────────

def receivable_rows(cid, start, end):
    """Parcelas de SO a receber com vencimento no período."""
    pmts = (OrderPayment.query
            .join(Order, OrderPayment.order_id == Order.id)
            .filter(Order.company_id == cid, Order.deleted_at.is_(None))
            .filter(Order.status.notin_(["cancelado", "excluido"]))
            .filter(OrderPayment.paid_at.is_(None))
            .filter(OrderPayment.amount > 0)
            .filter(OrderPayment.due_date.isnot(None))
            .filter(OrderPayment.due_date.between(start, end))
            .order_by(OrderPayment.due_date.asc())
            .all())
    rows = []
    for p in pmts:
        o = p.order
        rows.append(ReceivableRow(
            origem="SO",
            description=f"{o.number} — parcela {p.installment_no}",
            due_date=p.due_date,
            amount=float(p.amount or 0),
            so_number=o.number,
            client_name=o.client_name or "",
            payment=p,
        ))
    return rows


def receivable_totals(cid, start, end):
    """(a_receber, vencido) das obrigações do período."""
    rows = receivable_rows(cid, start, end)
    total = round(sum(r.amount for r in rows), 2)
    overdue = round(sum(r.amount for r in rows if r.is_overdue), 2)
    return total, overdue


def received_in_period(cid, start, end):
    """Recebido no período (caixa — FR revenue pago por paid_date)."""
    from ..extensions import db
    from sqlalchemy import func
    return (db.session.query(func.sum(FinancialRecord.amount))
            .filter(FinancialRecord.company_id == cid,
                    FinancialRecord.type == "revenue",
                    FinancialRecord.status == "pago",
                    FinancialRecord.deleted_at.is_(None),
                    FinancialRecord.paid_date.isnot(None),
                    FinancialRecord.paid_date.between(start, end))
            .scalar() or 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# AP — Contas a Pagar (Custos de Serviços + Despesas Gerais)
# ─────────────────────────────────────────────────────────────────────────────

def payable_cost_rows(cid, start, end):
    """Obrigações de PO (custos de serviços) com vencimento no período."""
    pmts = (POPayment.query
            .join(PurchaseOrder, POPayment.po_id == PurchaseOrder.id)
            .filter(PurchaseOrder.company_id == cid, PurchaseOrder.deleted_at.is_(None))
            .filter(PurchaseOrder.status.notin_(["cancelado", "excluido"]))
            .filter(POPayment.paid_at.is_(None))
            .filter(POPayment.amount > 0)
            .filter(POPayment.due_date.isnot(None))
            .filter(POPayment.due_date.between(start, end))
            .order_by(POPayment.due_date.asc())
            .all())
    rows = []
    for p in pmts:
        po = p.purchase_order
        rows.append(PayableRow(
            origem="PO",
            description=f"{po.number} — parcela {p.installment_no}",
            due_date=p.due_date,
            amount=float(p.amount or 0),
            po_number=po.number,
            supplier_name=po.supplier.name if po.supplier else "",
            payment=p,
        ))
    return rows


def payable_expense_rows(cid, start, end):
    """Despesas gerais pendentes com vencimento no período."""
    frs = (FinancialRecord.query
           .filter_by(company_id=cid, type="expense")
           .filter(FinancialRecord.deleted_at.is_(None))
           .filter(FinancialRecord.status == "pendente")
           .filter(FinancialRecord.due_date.isnot(None))
           .filter(FinancialRecord.due_date.between(start, end))
           .order_by(FinancialRecord.due_date.asc())
           .all())
    return [PayableRow(
        origem="DESPESA",
        description=fr.description or "Despesa",
        due_date=fr.due_date,
        amount=float(fr.amount or 0),
        supplier_name=fr.supplier.name if fr.supplier else "",
        expense=fr,
    ) for fr in frs]


def payable_rows(cid, start, end):
    """AP consolidado (custos + despesas), ordenado por vencimento."""
    rows = payable_cost_rows(cid, start, end) + payable_expense_rows(cid, start, end)
    return sorted(rows, key=lambda r: (r.due_date is None, r.due_date or _date.max))


def payable_totals(cid, start, end):
    """dict(total, custos, despesas, vencido) das obrigações do período."""
    costs = payable_cost_rows(cid, start, end)
    expenses = payable_expense_rows(cid, start, end)
    all_rows = costs + expenses
    return {
        "total": round(sum(r.amount for r in all_rows), 2),
        "custos": round(sum(r.amount for r in costs), 2),
        "despesas": round(sum(r.amount for r in expenses), 2),
        "vencido": round(sum(r.amount for r in all_rows if r.is_overdue), 2),
    }


def paid_in_period(cid, start, end):
    """Pago no período (caixa — FR cost+expense pago por paid_date)."""
    from ..extensions import db
    from sqlalchemy import func
    return (db.session.query(func.sum(FinancialRecord.amount))
            .filter(FinancialRecord.company_id == cid,
                    FinancialRecord.type.in_(["cost", "expense"]),
                    FinancialRecord.status == "pago",
                    FinancialRecord.deleted_at.is_(None),
                    FinancialRecord.paid_date.isnot(None),
                    FinancialRecord.paid_date.between(start, end))
            .scalar() or 0.0)
