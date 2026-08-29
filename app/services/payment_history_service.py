"""payment_history_service.py — Timeline de baixas para EXIBIÇÃO (Etapa 11B).

Fonte: audit_logs (eventos de parcela). SOMENTE LEITURA — nada é gravado.

Regras 11B-A1:
  * Pós-10D  ("Parcela N baixada R$ X"): linha completa (data, valor, saldo
    após DERIVADO em Python só para apresentação).
  * Pré-10D  ("Parcela N baixada" sem valor): linha sem valor individual —
    NUNCA inventar/ratear o total.
  * "Baixa registrada R$ X" (painel financeiro) é IGNORADA (outro fluxo).
  * Inconsistências (soma > valor, saldo < 0) NÃO são corrigidas — apenas
    sinalizadas para a UI.
"""
import re

_BAIXA_RE = re.compile(r"Parcela\s+(\d+)\s+baixada(?:\s+R\$\s*([\d.,]+))?", re.IGNORECASE)


def build_baixa_history(audit_logs, payments_by_no: dict, user_names: dict = None) -> dict:
    """Monta o histórico de baixas por parcela.

    Args:
        audit_logs: lista de AuditLog (já filtrados por entity/entity_id).
        payments_by_no: dict {installment_no: OrderPayment|POPayment}.
        user_names: dict opcional {user_id: nome}.

    Returns:
        {installment_no: {
            "entries": [{"at": datetime, "user": str, "value": float|None,
                         "balance_after": float|None}],
            "pre_10d": bool,          # existe evento sem valor individual
            "consistent": bool,       # soma dos valores bate com paid_amount
            "total": float,           # soma dos valores conhecidos
            "final_paid": float,      # paid_amount da parcela (comprovado)
            "amount": float,          # valor original da parcela
        }}
    """
    history = {}
    user_names = user_names or {}

    for log in audit_logs:
        m = _BAIXA_RE.search(log.action or "")
        if not m:
            continue  # ignora "Baixa registrada R$ X" (painel) e demais ações
        try:
            no = int(m.group(1))
        except (TypeError, ValueError):
            continue
        value_raw = m.group(2)
        value = None
        if value_raw:
            try:
                if "," in value_raw:
                    # formato 1.300,00 (milhar com ponto, decimal com vírgula)
                    value = float(value_raw.replace(".", "").replace(",", "."))
                else:
                    # formato 500.00 (ponto decimal, padrão do f-string do log)
                    value = float(value_raw)
            except ValueError:
                value = None
        h = history.setdefault(no, {
            "entries": [], "pre_10d": False, "consistent": True,
            "total": 0.0, "final_paid": 0.0, "amount": 0.0,
        })
        h["entries"].append({
            "at": log.created_at,
            "user": user_names.get(log.user_id, f"Usuário {log.user_id}"),
            "value": value,
            "balance_after": None,
        })
        if value is None:
            h["pre_10d"] = True

    # Completa com os dados COMPROVADOS da parcela e deriva saldo após (exibição)
    for no, h in history.items():
        pmt = payments_by_no.get(no)
        if pmt is None:
            h["consistent"] = False
            continue
        amount = float(pmt.amount or 0.0)
        h["amount"] = amount
        h["final_paid"] = float(pmt.paid_amount or 0.0)

        running = 0.0
        all_valued = True
        for e in h["entries"]:
            if e["value"] is not None:
                running = round(running + e["value"], 2)
                e["balance_after"] = round(amount - running, 2)
            else:
                all_valued = False
        h["total"] = running

        if all_valued:
            # consistência: soma dos eventos conhecidos vs acumulado real
            h["consistent"] = (abs(running - h["final_paid"]) <= 0.005
                               and running <= amount + 0.005)
        else:
            h["consistent"] = h["final_paid"] <= amount + 0.005

    return history
