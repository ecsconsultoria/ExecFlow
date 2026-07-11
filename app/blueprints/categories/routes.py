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
        new_name = (request.form.get("name") or "").strip()
        new_desc = (request.form.get("description") or "").strip()

        if cid:
            # ── EDIÇÃO ──────────────────────────────────────────────
            cat = VehicleCategory.query.get_or_404(int(cid))
            if new_name and new_name != cat.name:
                existing = VehicleCategory.query.filter(
                    VehicleCategory.name == new_name, VehicleCategory.id != cat.id
                ).first()
                if existing:
                    flash("Já existe outra categoria com este nome.", "danger")
                    return redirect(url_for("categories.index"))
                cat.name = new_name
            cat.description = new_desc
            db.session.commit()
            log_activity("vehicle_category", cat.id, current_user.company_id,
                         f"Categoria {cat.name!r} — modelo atualizado", current_user.id)
            flash(f"Categoria '{cat.name}' atualizada.", "success")
        else:
            # ── CRIAÇÃO ─────────────────────────────────────────────
            if not new_name:
                flash("Nome da categoria é obrigatório.", "danger")
                return redirect(url_for("categories.index"))
            existing = VehicleCategory.query.filter_by(name=new_name).first()
            if existing:
                flash("Já existe uma categoria com este nome.", "danger")
                return redirect(url_for("categories.index"))
            # Gera slug a partir do nome
            import re
            slug = re.sub(r'[^a-z0-9]+', '-', new_name.lower().strip()).strip('-')
            # Pega o maior sort_order + 1
            max_sort = db.session.query(db.func.max(VehicleCategory.sort_order)).scalar() or 0
            cat = VehicleCategory(
                name=new_name,
                slug=slug,
                description=new_desc,
                sort_order=max_sort + 1,
                is_active=True,
                category_type="transport",
            )
            db.session.add(cat)
            db.session.commit()
            log_activity("vehicle_category", cat.id, current_user.company_id,
                         f"Categoria {cat.name!r} criada", current_user.id)
            flash(f"Categoria '{cat.name}' criada com sucesso.", "success")
        return redirect(url_for("categories.index"))

    # Tabela global — categorias são compartilhadas entre tenants
    categories = VehicleCategory.query.order_by(VehicleCategory.sort_order).all()
    return render_template("categories/index.html", categories=categories)
