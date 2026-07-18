"""Categories blueprint — tabelas globais (sem multi-tenant).

VehicleCategory é uma tabela de referência global: as categorias
(Executivo, Sedan, Van, etc.) são compartilhadas entre todas as empresas.
NÃO requer filtro company_id — esta é uma decisão de design intencional.
"""
from flask import render_template, request, redirect, url_for, flash, send_file, make_response
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


@categories_bp.route("/sign", methods=["GET", "POST"])
@login_required
def sign():
    if request.method == "POST":
        text = (request.form.get("sign_text") or "").strip()

        # Upload de imagem
        img_path = ""
        _img_file = request.files.get("sign_image")
        if _img_file and _img_file.filename:
            import uuid, os as _os
            from flask import current_app
            ext = _os.path.splitext(_img_file.filename)[1].lower()
            if ext in ('.png', '.jpg', '.jpeg'):
                fname = f"sign_{uuid.uuid4().hex[:8]}{ext}"
                up_dir = current_app.config["UPLOAD_FOLDER"]
                _os.makedirs(up_dir, exist_ok=True)
                dest = _os.path.join(up_dir, fname)
                _img_file.save(dest)
                img_path = f"/uploads/{fname}"

        img_pos = request.form.get("sign_img_pos", "abaixo")

        if not text and not img_path:
            flash("Preencha o texto ou selecione uma imagem.", "warning")
            return redirect(url_for("categories.sign"))

        from ...services.purchase_order_pdf import generate_sign_pdf
        buf = generate_sign_pdf(text=text, img_path=img_path, img_pos=img_pos)
        resp = make_response(send_file(buf, mimetype="application/pdf",
                               as_attachment=True, download_name="placa_receptivo.pdf"))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    return render_template("categories/sign.html")
