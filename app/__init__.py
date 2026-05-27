import os
from flask import Flask, send_from_directory
from .extensions import db, migrate, login_manager
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

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    register_blueprints(app)

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
                                billing_label, status_badge_class)
    app.jinja_env.filters["to_br"]        = utc_to_br
    app.jinja_env.filters["currency"]     = format_currency
    app.jinja_env.filters["fdate"]        = format_date
    app.jinja_env.filters["fdatetime"]    = format_datetime
    app.jinja_env.filters["billing_label"]= billing_label
    app.jinja_env.filters["status_badge"] = status_badge_class

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

    with app.app_context():
        from . import models  # noqa
        db.create_all()
        _ensure_schema_columns()
        _seed_initial_data(app)

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
