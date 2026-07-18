import os
from flask import Flask, send_from_directory
from .extensions import db, migrate, login_manager, csrf
from .blueprints import register_blueprints


def create_app(config_name: str | None = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__, template_folder="templates", static_folder="static")

    from config import config
    cfg = config.get(config_name, config["default"])
    app.config.from_object(cfg)

    instance = cfg()
    if hasattr(instance, "SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = instance.SQLALCHEMY_DATABASE_URI
    if hasattr(instance, "SQLALCHEMY_ENGINE_OPTIONS"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = instance.SQLALCHEMY_ENGINE_OPTIONS

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # ── SQLite: enable WAL + sane PRAGMAs to avoid "database is locked" ──
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    import sqlite3 as _sqlite3

    @event.listens_for(Engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _rec):
        if isinstance(dbapi_conn, _sqlite3.Connection):
            try:
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL;")
                cur.execute("PRAGMA synchronous=NORMAL;")
                cur.execute("PRAGMA busy_timeout=30000;")
                cur.execute("PRAGMA foreign_keys=ON;")
                cur.close()
            except Exception:
                pass

    register_blueprints(app)

    # ── Phase 8: security headers (X-Frame, nosniff, Referrer-Policy, etc.) ──
    from .utils.security import register_security_headers
    register_security_headers(app)

    # ── Persistent upload folder ──────────────────────────────────────────────
    # In production set env var UPLOAD_FOLDER=/orcamentos/uploads (Render disk).
    # Locally falls back to app/static/uploads so dev works without any config.
    _static_uploads = os.path.join(app.root_path, "static", "uploads")
    _upload_folder = app.config.get("UPLOAD_FOLDER") or _static_uploads
    try:
        os.makedirs(_upload_folder, exist_ok=True)
    except PermissionError:
        # Configured path not available (e.g. disk not mounted); fall back gracefully.
        _upload_folder = _static_uploads
        os.makedirs(_upload_folder, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = _upload_folder

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    # Jinja2 filters
    from .utils import utc_to_br
    from .utils.helpers import (format_currency, format_date, format_datetime,
                                billing_label, status_badge_class,
                                status_badge_style, status_dot_color)
    app.jinja_env.filters["to_br"]           = utc_to_br
    app.jinja_env.filters["currency"]        = format_currency
    app.jinja_env.filters["fdate"]           = format_date
    app.jinja_env.filters["fdatetime"]       = format_datetime
    app.jinja_env.filters["billing_label"]   = billing_label
    app.jinja_env.filters["status_badge"]    = status_badge_class
    app.jinja_env.filters["status_badge_style"] = status_badge_style
    app.jinja_env.filters["status_dot_color"]   = status_dot_color

    @app.context_processor
    def _inject_company():
        from flask_login import current_user
        from .models.company import Company as _Company
        try:
            if current_user.is_authenticated:
                return {"current_company": _Company.query.get(current_user.company_id)}
        except Exception:
            pass
        return {"current_company": None}

    @app.before_request
    def _enforce_password_change():
        """Força usuários com must_change_password a trocar antes de seguir."""
        from flask import request, redirect, url_for
        from flask_login import current_user
        try:
            if not current_user.is_authenticated:
                return None
            if not getattr(current_user, "must_change_password", False):
                return None
            allowed = {
                "auth.change_password", "auth.logout", "auth.login",
                "static", "uploaded_file",
            }
            if request.endpoint in allowed:
                return None
            return redirect(url_for("auth.change_password"))
        except Exception:
            return None

    @app.context_processor
    def _inject_rbac_helpers():
        """Expe `has_perm` / `has_any_perm` aos templates (UX only).

        IMPORTANTE: estes helpers são apenas para esconder/exibir elementos
        na UI. A segurança real é server-side via @require_permission.
        """
        from flask_login import current_user

        def _has_perm(code):
            try:
                if not current_user.is_authenticated:
                    return False
                return current_user.has_permission(code)
            except Exception:
                return False

        def _has_any_perm(*codes):
            try:
                if not current_user.is_authenticated:
                    return False
                return any(current_user.has_permission(c) for c in codes)
            except Exception:
                return False

        def _has_role(code):
            try:
                if not current_user.is_authenticated:
                    return False
                return current_user.has_role(code)
            except Exception:
                return False

        return {"has_perm": _has_perm, "has_any_perm": _has_any_perm, "has_role": _has_role}

    with app.app_context():
        from . import models  # noqa
        db.create_all()
        _ensure_schema_columns()
        _seed_initial_data(app)
        _seed_rbac(app)

    return app


def _ensure_schema_columns():
    """Safely add any model columns missing from an existing DB.

    db.create_all() only creates new tables — it will never ALTER an existing
    table to add new columns.  This function bridges that gap so that Render
    (and any other deployment that skips `flask db upgrade`) stays in sync with
    the SQLAlchemy models.
    """
    import logging
    log = logging.getLogger(__name__)
    try:
        from sqlalchemy import inspect as _inspect, text as _text
        insp = _inspect(db.engine)
        table_names = set(insp.get_table_names())

        # ── services: operational flag columns added 2026-05-23 ───────────────
        _NEW_SERVICE_COLS = [
            'is_operational',
            'requires_route',
            'requires_passenger',
            'requires_vehicle',
            'requires_dispatch',
            'requires_schedule',
        ]
        if 'services' in table_names:
            existing = {c['name'] for c in insp.get_columns('services')}
            with db.engine.begin() as conn:
                for col in _NEW_SERVICE_COLS:
                    if col not in existing:
                        conn.execute(_text(
                            f'ALTER TABLE services ADD COLUMN {col} BOOLEAN DEFAULT FALSE'
                        ))
                        log.info('Schema patch applied: services.%s', col)

        # ── orders: other_costs_label column added 2026-05-24 ─────────────────
        if 'orders' in table_names:
            existing_o = {c['name'] for c in insp.get_columns('orders')}
            if 'other_costs_label' not in existing_o:
                with db.engine.begin() as conn:
                    conn.execute(_text(
                        "ALTER TABLE orders ADD COLUMN other_costs_label VARCHAR(200) DEFAULT ''"
                    ))
                log.info('Schema patch applied: orders.other_costs_label')

        # ── order_items: operational item columns (SO por item) ──────────────
        if 'order_items' in table_names:
            existing_oi = {c['name'] for c in insp.get_columns('order_items')}
            new_item_cols = [
                ('op_driver_name', 'VARCHAR(200)'),
                ('op_driver_phone', 'VARCHAR(50)'),
                ('op_vehicle_model', 'VARCHAR(200)'),
                ('op_vehicle_plate', 'VARCHAR(20)'),
                ('op_pickup_datetime', 'TIMESTAMP'),
                ('op_pickup_location', 'TEXT'),
                ('op_dropoff_location', 'TEXT'),
                ('op_passenger_name', 'VARCHAR(200)'),
                ('op_passenger_phone', 'VARCHAR(50)'),
                ('op_flight_number', 'VARCHAR(50)'),
                ('op_notes', 'VARCHAR(500)'),
            ]
            with db.engine.begin() as conn:
                for col_name, col_type in new_item_cols:
                    if col_name not in existing_oi:
                        conn.execute(_text(
                            f'ALTER TABLE order_items ADD COLUMN {col_name} {col_type}'
                        ))
                        log.info('Schema patch applied: order_items.%s', col_name)

        # ── po_items: operational item columns (PO por item) ─────────────────
        if 'po_items' in table_names:
            existing_pi = {c['name'] for c in insp.get_columns('po_items')}
            new_po_item_cols = [
                ('op_driver_name', 'VARCHAR(200)'),
                ('op_driver_phone', 'VARCHAR(50)'),
                ('op_vehicle_model', 'VARCHAR(200)'),
                ('op_vehicle_plate', 'VARCHAR(20)'),
                ('op_pickup_datetime', 'TIMESTAMP'),
                ('op_pickup_location', 'TEXT'),
                ('op_dropoff_location', 'TEXT'),
                ('op_passenger_name', 'VARCHAR(200)'),
                ('op_passenger_phone', 'VARCHAR(50)'),
                ('op_flight_number', 'VARCHAR(50)'),
                ('op_pax_count', 'INTEGER'),
                ('op_notes', 'VARCHAR(500)'),
            ]
            with db.engine.begin() as conn:
                for col_name, col_type in new_po_item_cols:
                    if col_name not in existing_pi:
                        conn.execute(_text(
                            f'ALTER TABLE po_items ADD COLUMN {col_name} {col_type}'
                        ))
                        log.info('Schema patch applied: po_items.%s', col_name)

        # ── users: must_change_password flag (force password change on first login) ─
        if 'users' in table_names:
            existing_u = {c['name'] for c in insp.get_columns('users')}
            if 'must_change_password' not in existing_u:
                with db.engine.begin() as conn:
                    conn.execute(_text(
                        "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE"
                    ))
                log.info('Schema patch applied: users.must_change_password')

        # ── financial_records: soft delete column ──────────────────────────────────
        if 'financial_records' in table_names:
            existing_fr = {c['name'] for c in insp.get_columns('financial_records')}
            if 'deleted_at' not in existing_fr:
                with db.engine.begin() as conn:
                    conn.execute(_text(
                        "ALTER TABLE financial_records ADD COLUMN deleted_at TIMESTAMP"
                    ))
                log.info('Schema patch applied: financial_records.deleted_at')

        # ── purchase_orders: reopened_at / reopened_by (2026-06-16) ──────────
        if 'purchase_orders' in table_names:
            existing_po = {c['name'] for c in insp.get_columns('purchase_orders')}
            _po_new_cols = [
                ('reopened_at', 'TIMESTAMP'),
                ('reopened_by', 'INTEGER'),
                ('delivery_date', 'DATE'),
            ]
            with db.engine.begin() as conn:
                for col_name, col_type in _po_new_cols:
                    if col_name not in existing_po:
                        conn.execute(_text(
                            f'ALTER TABLE purchase_orders ADD COLUMN {col_name} {col_type}'
                        ))
                        log.info('Schema patch applied: purchase_orders.%s', col_name)

        # ── service_pricing: fix driver_type typo 'Bilingue' → 'Bilíngue' ────
        if 'service_pricing' in table_names:
            with db.engine.begin() as conn:
                conn.execute(_text(
                    "UPDATE service_pricing SET driver_type = 'Bilíngue'"
                    " WHERE driver_type = 'Bilingue'"
                ))
    except Exception as exc:
        log.warning('_ensure_schema_columns failed: %s', exc)


def _seed_initial_data(app: Flask):
    from .models.service import State
    if State.query.count() > 0:
        return
    _do_seed()


def _do_seed():
    import os
    from .extensions import db as _db
    from .models.vehicle import VehicleCategory, CATEGORIES
    from .models.service import State, Service, ServicePricing
    from .models.company import Company
    from .models.user import User

    sp = State(code="SP", name="São Paulo")
    rj = State(code="RJ", name="Rio de Janeiro")
    _db.session.add_all([sp, rj])
    _db.session.flush()
    state_map = {"SP": sp.id, "RJ": rj.id}

    for i, name in enumerate(CATEGORIES):
        slug = (name.lower()
                .replace(" ", "_")
                .translate(str.maketrans("ôêâãúóéíàü", "oeaauoeiau")))
        _db.session.add(VehicleCategory(name=name, slug=slug, sort_order=i))
    _db.session.flush()
    cat_map = {c.name: c.id for c in VehicleCategory.query.all()}

    proj_root  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tabela_path = os.path.join(proj_root, "tabela_data.py")

    rows = []
    if os.path.exists(tabela_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tabela_data", tabela_path)
        td   = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(td)
        rows = td.TABELA_2026

    svc_map = {}
    for (svc_name, vehicle, driver_type, price_cost, price_base, state_code) in rows:
        key = (svc_name, state_code)
        if key not in svc_map:
            sid = state_map.get(state_code)
            if sid:
                svc = Service(name=svc_name, state_id=sid, is_active=True)
                _db.session.add(svc)
                _db.session.flush()
                svc_map[key] = svc.id

    for (svc_name, vehicle, driver_type, price_cost, price_base, state_code) in rows:
        key    = (svc_name, state_code)
        svc_id = svc_map.get(key)
        cat_id = cat_map.get(vehicle)
        if not svc_id or not cat_id:
            continue
        p = ServicePricing(
            service_id      = svc_id,
            category_id     = cat_id,
            driver_type     = driver_type or "",
            price_cost      = price_cost,
            price_base      = price_base,
            price_nf        = round(price_base * 1.10, 2),
            price_cartao    = round(price_base * 1.065, 2),
            price_nf_cartao = round(price_base * 1.165, 2),
            is_active       = True,
        )
        _db.session.add(p)

    if Company.query.count() == 0:
        company = Company(name="Executive Car SP", slug="executivecars",
                          document="11.183.125/0001-10")
        _db.session.add(company)
        _db.session.flush()

        admin = User(company_id=company.id, name="Admin",
                     email="admin@executivecarsp.com", role="superadmin")
        admin.set_password("admin123")
        _db.session.add(admin)

    _db.session.commit()


def _seed_rbac(app: Flask):
    """Cria/atualiza Permissions, Roles canônicas e suas associações.

    Idempotente: pode rodar a cada boot. Também migra usuários legados que
    ainda não têm Role atribuído (User.role string → Role objects).
    """
    import logging
    log = logging.getLogger(__name__)
    try:
        from .models.rbac import Role, Permission
        from .models.user import User
        from .utils.permissions import (
            PERMISSION_CATALOG, SYSTEM_ROLES,
            ROLE_PERMISSION_MATRIX, LEGACY_ROLE_MAP,
        )

        # 1) Upsert Permissions
        existing_perms = {p.code: p for p in Permission.query.all()}
        for code, category, label, desc in PERMISSION_CATALOG:
            p = existing_perms.get(code)
            if p is None:
                p = Permission(code=code, category=category, label=label, description=desc)
                db.session.add(p)
                existing_perms[code] = p
            else:
                p.category    = category
                p.label       = label
                p.description = desc
        db.session.flush()

        # 2) Upsert Roles canônicas + sincroniza permissões
        existing_roles = {r.code: r for r in Role.query.all()}
        for code, label, desc in SYSTEM_ROLES:
            r = existing_roles.get(code)
            if r is None:
                r = Role(code=code, label=label, description=desc, is_system=True)
                db.session.add(r)
                existing_roles[code] = r
            else:
                r.label       = label
                r.description = desc
                r.is_system   = True
            # sync permissions desta role
            wanted_codes = ROLE_PERMISSION_MATRIX.get(code, set())
            r.permissions = [existing_perms[c] for c in wanted_codes if c in existing_perms]
        db.session.flush()

        # 3) Migração one-shot: users sem roles → mapear pela coluna legada
        users_without_roles = User.query.filter(~User.roles.any()).all()
        for u in users_without_roles:
            target_code = LEGACY_ROLE_MAP.get((u.role or "").lower())
            if target_code and target_code in existing_roles:
                u.roles.append(existing_roles[target_code])
                log.info("RBAC migration: user %s (legacy=%s) → role %s",
                         u.email, u.role, target_code)

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        log.warning("_seed_rbac failed: %s", exc)
