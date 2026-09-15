"""tests/test_recorrencia_despesas.py — recorrência de despesas (Etapa 14).

Cobre: criação com recorrência (mensal/anual), geração da próxima ocorrência
pela rota, corrente ativa só no elo mais recente, data-limite, cancelada não
gera, e next_emission em fim de mês.
"""
from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models.financial import FinancialRecord
from app.models.financial_catalog import FinancialCategory, CostCenter
from app.models.user import User
from app.services import recurrence_service

ADMIN_EMAIL = "admin@executivecarsp.com"
ADMIN_PWD = "admin123"


@pytest.fixture(scope="session")
def testing_app():
    return create_app("testing")


@pytest.fixture(autouse=True)
def clean(testing_app):
    with testing_app.app_context():
        for model in (FinancialRecord, CostCenter, FinancialCategory):
            model.query.delete()
        db.session.commit()
    yield


def _login(app):
    c = app.test_client()
    c.post("/auth/login", data={"email": ADMIN_EMAIL, "password": ADMIN_PWD},
           follow_redirects=False)
    return c


def _seed_catalog(app):
    with app.app_context():
        cid = User.query.filter_by(email=ADMIN_EMAIL).first().company_id
        cat = FinancialCategory(company_id=cid, name="Pessoal", type="expense", active=True)
        db.session.add(cat)
        db.session.flush()
        cc = CostCenter(company_id=cid, name="Administrativo", active=True)
        db.session.add(cc)
        db.session.commit()
        return cid, cat.id, cc.id


def _nova(app, c, cid, cat_id, cc_id, *, emission="2026-08-14", due="2026-08-14",
          recurrence="", until="", desc="Pró-Labore", valor="3025,00"):
    return c.post("/financial/expenses/new", data={
        "description": desc, "amount": valor,
        "emission_date": emission, "due_date": due,
        "financial_category_id": str(cat_id), "cost_center_id": str(cc_id),
        "supplier_id": "", "notes": "",
        "recurrence": recurrence, "recurrence_until": until,
    }, follow_redirects=False)


def test_next_emission_end_of_month():
    assert recurrence_service.next_emission(date(2026, 1, 31), "monthly") == date(2026, 2, 28)
    assert recurrence_service.next_emission(date(2026, 8, 14), "monthly") == date(2026, 9, 14)
    assert recurrence_service.next_emission(date(2026, 8, 14), "yearly") == date(2027, 8, 14)
    assert recurrence_service.next_emission(date(2024, 2, 29), "yearly") == date(2025, 2, 28)


def test_create_monthly_and_generate(testing_app):
    cid, cat_id, cc_id = _seed_catalog(testing_app)
    c = _login(testing_app)
    r = _nova(testing_app, c, cid, cat_id, cc_id, recurrence="monthly")
    assert r.status_code == 302

    with testing_app.app_context():
        elo = FinancialRecord.query.filter_by(description="Pró-Labore").one()
        assert elo.recurrence == "monthly" and elo.recurrence_active is True
        assert elo.next_run == date(2026, 9, 14)

        # gera a ocorrencia vencida
        criadas = recurrence_service.generate_due(cid, today=date(2026, 9, 14))
        assert len(criadas) == 1
        novo = criadas[0]
        assert novo.emission_date == date(2026, 9, 14)
        assert novo.due_date == date(2026, 9, 14)
        assert novo.amount == 3025.0 and novo.status == "pendente"
        assert novo.reference == f"expense:{novo.id}"
        assert novo.next_run == date(2026, 10, 14)
        # o elo antigo desativa; o novo e o ativo
        db.session.refresh(elo)
        assert elo.recurrence_active is False
        assert novo.recurrence_active is True

        # nao gera de novo no mesmo dia
        assert recurrence_service.generate_due(cid, today=date(2026, 9, 14)) == []


def test_yearly_and_until(testing_app):
    cid, cat_id, cc_id = _seed_catalog(testing_app)
    c = _login(testing_app)
    r = _nova(testing_app, c, cid, cat_id, cc_id, emission="2026-08-14", due="2026-08-14",
              recurrence="yearly", until="2028-01-01", desc="IPVA")
    assert r.status_code == 302

    with testing_app.app_context():
        elo = FinancialRecord.query.filter_by(description="IPVA").one()
        assert elo.next_run == date(2027, 8, 14)
        criadas = recurrence_service.generate_due(cid, today=date(2027, 8, 14))
        assert len(criadas) == 1
        assert criadas[0].emission_date == date(2027, 8, 14)
        assert criadas[0].next_run == date(2028, 8, 14)
        # passou da data-limite: encerra sem gerar
        assert recurrence_service.generate_due(cid, today=date(2029, 1, 1)) == []


def test_cancelada_nao_gera(testing_app):
    cid, cat_id, cc_id = _seed_catalog(testing_app)
    c = _login(testing_app)
    _nova(testing_app, c, cid, cat_id, cc_id, recurrence="monthly", desc="Assinatura")
    with testing_app.app_context():
        elo = FinancialRecord.query.filter_by(description="Assinatura").one()
        elo.status = "cancelado"
        db.session.commit()
        assert recurrence_service.generate_due(cid, today=date(2026, 9, 14)) == []


def test_botao_rota(testing_app):
    cid, cat_id, cc_id = _seed_catalog(testing_app)
    c = _login(testing_app)
    _nova(testing_app, c, cid, cat_id, cc_id, recurrence="monthly", desc="Consórcio")
    r = c.post("/financial/expenses/run-recurrences", follow_redirects=False)
    assert r.status_code == 302
    with testing_app.app_context():
        assert FinancialRecord.query.filter_by(description="Consórcio").count() == 2
