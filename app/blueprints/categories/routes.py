"""Categories blueprint — tabelas globais (sem multi-tenant).

VehicleCategory é uma tabela de referência global: as 18 categorias
(Executivo, Sedan, Van, etc.) são compartilhadas entre todas as empresas.
NÃO requer filtro company_id — esta é uma decisão de design intencional.
"""
from flask import render_template
from flask_login import login_required
from . import categories_bp
from ...models.vehicle import VehicleCategory
from ...utils.decorators import require_permission


@categories_bp.route("/")
@login_required
@require_permission("catalog.view")
def index():
    # Tabela global — categorias são compartilhadas entre tenants
    categories = VehicleCategory.query.order_by(VehicleCategory.sort_order).all()
    return render_template("categories/index.html", categories=categories)
