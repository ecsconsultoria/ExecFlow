"""Tenant isolation — Phase 7.

Cria uma segunda empresa + ServicePricing pertencente a ela e confirma que
o usuário OPERATIONAL/VIEWER da empresa principal NÃO consegue editar nem
excluir esse pricing (deve retornar 404).
"""
from __future__ import annotations
import pytest
from app.extensions import db
from app.models.company import Company
from app.models.service import Service, ServicePricing, State
from app.models.vehicle import VehicleCategory


@pytest.fixture
def other_company_pricing(app):
    """Cria empresa-fantasma + 1 ServicePricing exclusivo dela. Yield (pid)."""
    with app.app_context():
        other = Company.query.filter_by(name="Tenant Isolation Co.").first()
        if other is None:
            other = Company(name="Tenant Isolation Co.", slug="tenant-iso-test")
            db.session.add(other)
            db.session.flush()

        state = State.query.first()
        cat = VehicleCategory.query.first()
        assert state and cat, "Seed básico (state/category) ausente"

        svc = (Service.query
               .filter_by(company_id=other.id, name="ISO_TEST_SERVICE",
                          state_id=state.id)
               .first())
        if svc is None:
            svc = Service(company_id=other.id, state_id=state.id,
                          name="ISO_TEST_SERVICE", is_active=True)
            db.session.add(svc)
            db.session.flush()

        p = (ServicePricing.query
             .filter_by(service_id=svc.id, category_id=cat.id, driver_type="")
             .first())
        if p is None:
            p = ServicePricing(service_id=svc.id, category_id=cat.id,
                               driver_type="", price_cost=10, price_base=20,
                               is_active=True)
            db.session.add(p)
            db.session.commit()
        pid = p.id
    yield pid
    # cleanup mantém o registro: outros testes podem reutilizar (idempotente)


def test_cross_tenant_edit_returns_404(operational_client, other_company_pricing):
    pid = other_company_pricing
    r = operational_client.post(f"/services/edit/{pid}",
                                data={"price_cost": 99, "price_base": 199},
                                follow_redirects=False)
    # 404 (tenant block) ou 403 (sem perm) — ambos significam acesso negado.
    # OPERATIONAL tem catalog.manage no setup atual? Não — então 403 também ok.
    assert r.status_code in (403, 404), (
        f"Esperava bloqueio, recebeu {r.status_code} — possível leak cross-tenant!"
    )


def test_cross_tenant_delete_returns_404(operational_client, other_company_pricing):
    pid = other_company_pricing
    r = operational_client.post(f"/services/delete/{pid}", follow_redirects=False)
    assert r.status_code in (403, 404), (
        f"Esperava bloqueio, recebeu {r.status_code} — possível leak cross-tenant!"
    )


def test_admin_with_full_perms_still_blocked_by_tenant(admin_client, other_company_pricing):
    """Mesmo o admin (com catalog.manage) NÃO deve conseguir editar pricing
    de outra empresa — prova que o gate é tenant, não apenas permissão."""
    pid = other_company_pricing
    r = admin_client.post(f"/services/edit/{pid}",
                          data={"price_cost": 99, "price_base": 199},
                          follow_redirects=False)
    assert r.status_code == 404, (
        f"LEAK CROSS-TENANT: admin de outra empresa conseguiu editar (status={r.status_code})"
    )
    r2 = admin_client.post(f"/services/delete/{pid}", follow_redirects=False)
    assert r2.status_code == 404, (
        f"LEAK CROSS-TENANT: admin de outra empresa conseguiu deletar (status={r2.status_code})"
    )


def test_cross_tenant_pricing_not_in_listing(viewer_client, other_company_pricing, app):
    """A listagem /services/ não deve incluir o pricing da outra empresa."""
    pid = other_company_pricing
    r = viewer_client.get("/services/")
    assert r.status_code == 200
    # O ID isolado não pode aparecer como atributo data-id nem em form action
    body = r.get_data(as_text=True)
    needles = [f"/services/edit/{pid}", f"/services/delete/{pid}",
               f'data-id="{pid}"', f"value=\"{pid}\""]
    leaked = [n for n in needles if n in body]
    assert not leaked, f"Listagem expôs pricing de outra empresa: {leaked}"
