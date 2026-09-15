"""recurrence_service.py — recorrência de despesas (Etapa 14).

A corrente vive no registro mais recente: ele carrega recurrence_active=True
e next_run = data da próxima ocorrência. Quando next_run chega, generate_due()
cria o registro do período (copiando descrição/valor/categoria/centro/
fornecedor), desativa o elo anterior e o novo passa a ser o elo ativo.
"""
import calendar
from datetime import date, timedelta

from ..extensions import db
from ..models.financial import FinancialRecord
from ..utils import now_br

RECURRENCE_CHOICES = ("monthly", "yearly")


def next_emission(emission: date, recurrence: str) -> date:
    """Data da próxima ocorrência a partir de uma emissão."""
    if recurrence == "yearly":
        try:
            return emission.replace(year=emission.year + 1)
        except ValueError:  # 29/02 → 28/02 do ano seguinte
            return emission.replace(year=emission.year + 1, day=28)
    # monthly: mesmo dia no mês seguinte (dia 31 cai para o último dia do mês)
    m = (emission.month - 1 + 1) % 12 + 1
    y = emission.year + (1 if emission.month == 12 else 0)
    return emission.replace(year=y, month=m,
                            day=min(emission.day, calendar.monthrange(y, m)[1]))


def generate_due(cid, today=None) -> list:
    """Gera as ocorrências vencidas (next_run <= hoje) das despesas recorrentes.

    Retorna a lista de FinancialRecord criadas (já commitadas).
    """
    today = today or now_br().date()
    elos = (FinancialRecord.query
            .filter_by(company_id=cid, type="expense")
            .filter(FinancialRecord.deleted_at.is_(None))
            .filter(FinancialRecord.status != "cancelado")
            .filter(FinancialRecord.recurrence.in_(RECURRENCE_CHOICES))
            .filter(FinancialRecord.recurrence_active.is_(True))
            .filter(FinancialRecord.next_run.isnot(None))
            .filter(FinancialRecord.next_run <= today)
            .all())

    criadas = []
    for elo in elos:
        if elo.recurrence_until and elo.next_run > elo.recurrence_until:
            # passou da data-limite: encerra a corrente sem gerar
            elo.recurrence_active = False
            continue
        novo_emission = elo.next_run
        delta_dias = ((elo.due_date - elo.emission_date).days
                      if (elo.due_date and elo.emission_date) else 0)
        novo = FinancialRecord(
            company_id=elo.company_id, type="expense", category=elo.category,
            description=elo.description, amount=elo.amount, status="pendente",
            emission_date=novo_emission,
            due_date=novo_emission + timedelta(days=delta_dias),
            financial_category_id=elo.financial_category_id,
            cost_center_id=elo.cost_center_id,
            supplier_id=elo.supplier_id,
            recurrence=elo.recurrence,
            recurrence_until=elo.recurrence_until,
            recurrence_active=True,
            next_run=next_emission(novo_emission, elo.recurrence),
        )
        db.session.add(novo)
        db.session.flush()
        novo.reference = f"expense:{novo.id}"
        elo.recurrence_active = False   # o novo passa a ser o elo ativo
        criadas.append(novo)
    db.session.commit()
    return criadas
