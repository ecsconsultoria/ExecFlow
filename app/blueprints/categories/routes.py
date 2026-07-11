"""Categories blueprint — tabelas globais (sem multi-tenant).

VehicleCategory é uma tabela de referência global: as categorias
(Executivo, Sedan, Van, etc.) são compartilhadas entre todas as empresas.
NÃO requer filtro company_id — esta é uma decisão de design intencional.
"""
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import categories_bp
from ...models.vehicle import VehicleCategory
from ...extensions import db
from ...utils.decorators import require_permission
from ...utils.audit import log_activity


@categories_bp.route("/", methods=["GET", "POST"])
@login_required
@require_permission("catalog.view")
def index():
    if request.method == "POST":
        cid = request.form.get("category_id")
        cat = VehicleCategory.query.get_or_404(int(cid))
        # Atualiza description (modelo do veículo)
        cat.description = (request.form.get("description") or "").strip()
        # Opcional: atualiza name se enviado
        new_name = (request.form.get("name") or "").strip()
        if new_name and new_name != cat.name:
            existing = VehicleCategory.query.filter(
                VehicleCategory.name == new_name, VehicleCategory.id != cat.id
            ).first()
            if existing:
                flash("Já existe outra categoria com este nome.", "danger")
                return redirect(url_for("categories.index"))
            cat.name = new_name
        db.session.commit()
        log_activity("vehicle_category", cat.id, current_user.company_id,
                     f"Categoria {cat.name!r} — modelo atualizado", current_user.id)
        flash(f"Categoria '{cat.name}' atualizada.", "success")
        return redirect(url_for("categories.index"))

    # Tabela global — categorias são compartilhadas entre tenants
    categories = VehicleCategory.query.order_by(VehicleCategory.sort_order).all()
    return render_template("categories/index.html", categories=categories)
