"""tests/test_despesas_lote.py — pagamento em lote de despesas (Etapa 15)."""
import json
from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models.financial import FinancialRecord
from app.models.financial_catalog import FinancialCategory, CostCenter
from app.models.user import User

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


def _seed(app):
    with app.app_context():
        cid = User.query.filter_by(email=ADMIN_EMAIL).first().company_id
        cat = FinancialCategory(company_id=cid, name="Despesas Administrativas",
                                type="expense", active=True)
        db.session.add(cat)
        db.session.flush()
        cc = CostCenter(company_id=cid, name="Administrativo", active=True)
        db.session.add(cc)
        db.session.flush()
        ids = []
        for i, status in enumerate(("pendente", "pendente", "pago")):
            fr = FinancialRecord(company_id=cid, type="expense", category="outro",
                                 description=f"Conta {i}", amount=100.0 + i,
                                 status=status, emission_date=date(2026, 9, 1),
                                 due_date=date(2026, 9, 10),
                                 financial_category_id=cat.id, cost_center_id=cc.id,
                                 reference=f"expense:lote{i}")
            if status == "pago":
                fr.paid_date = date(2026, 9, 5)
            db.session.add(fr)
            db.session.flush()
            ids.append(fr.id)
        db.session.commit()
        return cid, cat.id, cc.id, ids


def test_bulk_baixa(testing_app):
    cid, cat_id, cc_id, ids = _seed(testing_app)
    c = _login(testing_app)
    r = c.post("/financial/expenses/bulk-baixa", data={
        "ids": json.dumps([ids[0], ids[1], ids[2]]),
        "paid_date": "2026-09-17",
        "payment_method": "PIX",
    }, follow_redirects=False)
    assert r.status_code == 302
    with testing_app.app_context():
        a, b, paga = (db.session.get(FinancialRecord, i) for i in ids)
        # as duas pendentes pagas em lote com a data informada
        assert a.status == "pago" and a.paid_date == date(2026, 9, 17)
        assert a.payment_method == "PIX"
        assert b.status == "pago" and b.paid_date == date(2026, 9, 17)
        # a ja paga manteve a data original (ignorada)
        assert paga.status == "pago" and paga.paid_date == date(2026, 9, 5)


def test_bulk_sem_ids(testing_app):
    _seed(testing_app)
    c = _login(testing_app)
    r = c.post("/financial/expenses/bulk-baixa", data={"ids": "[]"},
               follow_redirects=False)
    assert r.status_code == 302
    with testing_app.app_context():
        pendentes = FinancialRecord.query.filter_by(status="pendente").count()
        assert pendentes == 2  # nada mudou
