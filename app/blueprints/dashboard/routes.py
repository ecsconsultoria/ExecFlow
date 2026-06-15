from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from . import dashboard_bp
from ...utils.decorators import require_permission
from ...models.client        import Client
from ...models.quote         import Quote
from ...models.company       import Company
from ...models.service_order import ServiceOrder
from ...models.order         import Order, OrderPayment
from ...models.purchase_order import PurchaseOrder, POPayment
from ...models.driver        import Driver
from ...extensions           import db
from ...services             import margin_service
from ...services             import dispatch_service
from ...utils.audit          import log_activity
import os
import uuid


def _confirm_password_and_audit(action_label: str) -> bool:
    """Exige re-autenticação por senha antes de operações destrutivas.

    Retorna True se a senha confere e a auditoria foi registrada.
    Em caso de falha, faz flash + redirect e retorna False.
    O caller deve fazer `return redirect(...)` após receber False.
    """
    from flask import flash, redirect, url_for
    password = request.form.get("confirm_password", "")
    if not password or not current_user.check_password(password):
        flash("Senha de confirmação incorreta. Operação cancelada.", "danger")
        return False
    log_activity(
        "settings", current_user.company_id, current_user.company_id,
        f"RESET DESTRUTIVO: {action_label}",
        current_user.id,
    )
    return True


def _period_bounds(period: str, today):
    """Return (start_date, end_date, prev_start, prev_end) for the selected period."""
    from datetime import date
    from calendar import monthrange

    if period == "last_month":
        first_this = today.replace(day=1)
        prev_end   = first_this.replace(day=1) - __import__("datetime").timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        return prev_start, prev_end, None, None

    elif period == "last_30":
        end   = today
        start = today - __import__("datetime").timedelta(days=29)
        prev_end   = start - __import__("datetime").timedelta(days=1)
        prev_start = prev_end - __import__("datetime").timedelta(days=29)
        return start, end, prev_start, prev_end

    elif period == "quarter":
        q     = (today.month - 1) // 3
        start = today.replace(month=q * 3 + 1, day=1)
        pq    = q - 1
        if pq < 0:
            pq = 3
            py = today.year - 1
        else:
            py = today.year
        prev_start = date(py, pq * 3 + 1, 1)
        last_m = pq * 3 + 3
        prev_end   = date(py, last_m, monthrange(py, last_m)[1])
        return start, today, prev_start, prev_end

    elif period == "ytd":
        start = today.replace(month=1, day=1)
        prev_start = date(today.year - 1, 1, 1)
        prev_end   = date(today.year - 1, 12, 31)
        return start, today, prev_start, prev_end

    else:  # "this_month" (default)
        start = today.replace(day=1)
        prev_end   = start - __import__("datetime").timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        return start, today, prev_start, prev_end


def _so_revenue(cid, start, end):
    """Revenue = SUM(computed_total) for faturado/concluido SOs invoiced in period.

    Replicates Order.computed_total @property in SQL:
        total_amount
        - discount_amount  (= total_amount * pct/100  if discount_type=="%",  else flat value)
        + freight_amount
        + other_costs_amount
    """
    import sqlalchemy as sa
    from sqlalchemy import case, func
    from datetime import datetime

    disc_amt = case(
        (Order.discount_type == "%",
         func.coalesce(Order.total_amount, 0) * (func.coalesce(Order.discount_value, 0) / 100.0)),
        else_=func.coalesce(Order.discount_value, 0),
    )
    computed_total_expr = (
        func.coalesce(Order.total_amount, 0)
        - disc_amt
        + func.coalesce(Order.freight_amount, 0)
        + func.coalesce(Order.other_costs_amount, 0)
    )
    return (
        db.session.query(func.sum(computed_total_expr))
        .filter(
            Order.company_id == cid,
            Order.deleted_at.is_(None),
            Order.status.in_(["faturado", "concluido"]),
            Order.emission_date >= start,
            Order.emission_date <= end,
        )
        .scalar() or 0.0
    )


def _po_cost(cid, start, end):
    """Cost = SUM of POItem costs for faturado/pago POs emitted in period.
    Uses PO.created_at as the emission/accounting reference date."""
    import sqlalchemy as sa
    from ...models.purchase_order import POItem
    from datetime import datetime
    dt_start = datetime.combine(start, __import__("datetime").datetime.min.time())
    dt_end   = datetime.combine(end,   __import__("datetime").datetime.max.time())

    # Prefer item-level cost (more accurate, handles discounts)
    item_total = (
        db.session.query(sa.func.sum(POItem.unit_cost * POItem.quantity))
        .join(PurchaseOrder, POItem.po_id == PurchaseOrder.id)
        .filter(
            PurchaseOrder.company_id == cid,
            PurchaseOrder.deleted_at.is_(None),
            PurchaseOrder.status.in_(["concluido", "faturado", "pago"]),
            PurchaseOrder.created_at.between(dt_start, dt_end),
        )
        .scalar()
    )
    if item_total is not None:
        return float(item_total)

    # Fallback to PO.amount
    return (
        db.session.query(sa.func.sum(PurchaseOrder.amount))
        .filter(
            PurchaseOrder.company_id == cid,
            PurchaseOrder.deleted_at.is_(None),
            PurchaseOrder.status.in_(["concluido", "faturado", "pago"]),
            PurchaseOrder.created_at.between(dt_start, dt_end),
        )
        .scalar() or 0.0
    )


@dashboard_bp.route("/")
@login_required
def index():
    from ...utils import now_br
    from datetime import datetime, timedelta
    import sqlalchemy as sa
    import json

    cid    = current_user.company_id
    today  = now_br().date()
    period = request.args.get("period", "this_month")

    # ── Period bounds ─────────────────────────────────────────────────────────
    p_start, p_end, pp_start, pp_end = _period_bounds(period, today)

    # ── KPI: counts ──────────────────────────────────────────────────────────
    total_clients = Client.query.filter_by(company_id=cid, deleted_at=None).count()
    total_quotes  = Quote.query.filter_by(company_id=cid,  deleted_at=None).count()

    active_so_count = (Order.query
                       .filter_by(company_id=cid, deleted_at=None)
                       .filter(Order.status.in_(["novo", "aberto"]))
                       .count())

    open_po_count = (PurchaseOrder.query
                     .filter_by(company_id=cid, deleted_at=None)
                     .filter(PurchaseOrder.status.in_(["rascunho", "aberto", "aprovado", "em_execucao"]))
                     .count())

    pending_rfq_count = Quote.query.filter_by(company_id=cid, status="pendente", deleted_at=None).count()

    # ── KPI: financials (current period) ─────────────────────────────────────
    so_revenue = _so_revenue(cid, p_start, p_end)
    po_cost    = _po_cost(cid, p_start, p_end)
    margin_val = so_revenue - po_cost
    margin_pct = round(margin_val / so_revenue * 100, 1) if so_revenue else 0.0

    # Prior period for delta
    delta_revenue = delta_pct = None
    if pp_start and pp_end:
        prev_rev   = _so_revenue(cid, pp_start, pp_end)
        prev_cost  = _po_cost(cid, pp_start, pp_end)
        prev_margin = prev_rev - prev_cost
        if prev_rev:
            delta_revenue = round((so_revenue - prev_rev) / prev_rev * 100, 1)
        if prev_rev:
            prev_mpct = round(prev_margin / prev_rev * 100, 1)
            delta_pct = round(margin_pct - prev_mpct, 1)

    # ── 12-month rolling chart data ────────────────────────────────────────
    chart_rows = []
    for i in range(11, -1, -1):
        # compute month start/end for i months ago
        ref = today.replace(day=1) - timedelta(days=1) if i > 0 else today
        for _ in range(i):
            ref = ref.replace(day=1) - timedelta(days=1)
        m_start = ref.replace(day=1)
        from calendar import monthrange as _mr
        m_end   = m_start.replace(day=_mr(m_start.year, m_start.month)[1])
        rev  = _so_revenue(cid, m_start, m_end)
        cost = _po_cost(cid, m_start, m_end)
        chart_rows.append({
            "month": m_start.strftime("%b/%y"),
            "revenue": round(rev, 2),
            "cost": round(cost, 2),
            "margin_pct": round((rev - cost) / rev * 100, 1) if rev else 0.0,
        })
    chart_data_json = json.dumps(chart_rows)

    # ── Pipeline funnel ───────────────────────────────────────────────────────
    cutoff_30 = today - timedelta(days=30)
    funnel_sent_count = (Quote.query
                         .filter_by(company_id=cid, deleted_at=None)
                         .filter(Quote.created_at >= datetime.combine(cutoff_30, datetime.min.time()))
                         .count())
    funnel_sent_val = (db.session.query(sa.func.sum(Quote.total_amount))
                       .filter(Quote.company_id == cid, Quote.deleted_at.is_(None),
                               Quote.created_at >= datetime.combine(cutoff_30, datetime.min.time()))
                       .scalar() or 0.0)
    funnel_appr_count = (Quote.query
                         .filter_by(company_id=cid, deleted_at=None)
                         .filter(Quote.status.in_(["aprovado", "pago", "reserva_confirmada"]))
                         .count())
    funnel_appr_val = (db.session.query(sa.func.sum(Quote.total_amount))
                       .filter(Quote.company_id == cid, Quote.deleted_at.is_(None),
                               Quote.status.in_(["aprovado", "pago", "reserva_confirmada"]))
                       .scalar() or 0.0)
    funnel_so_count = (Order.query
                       .filter_by(company_id=cid, deleted_at=None)
                       .filter(Order.status.in_(["novo", "aberto", "faturado"]))
                       .count())
    funnel_so_val = (db.session.query(sa.func.sum(Order.total_amount))
                     .filter(Order.company_id == cid, Order.deleted_at.is_(None),
                             Order.status.in_(["novo", "aberto", "faturado"]))
                     .scalar() or 0.0)
    funnel_closed_count = (Order.query
                           .filter_by(company_id=cid, deleted_at=None)
                           .filter(Order.status == "concluido")
                           .count())
    funnel_closed_val = (db.session.query(sa.func.sum(Order.total_amount))
                         .filter(Order.company_id == cid, Order.deleted_at.is_(None),
                                 Order.status == "concluido")
                         .scalar() or 0.0)
    conversion_rate = round(funnel_appr_count / funnel_sent_count * 100) if funnel_sent_count else 0

    # ── Dispatch summary ──────────────────────────────────────────────────────
    dispatch_summary = dispatch_service.get_summary(cid, today)

    # ── Upcoming OS (7 days) ─────────────────────────────────────────────────
    week_end = today + timedelta(days=7)
    upcoming_os = (ServiceOrder.query
                   .filter_by(company_id=cid)
                   .filter(ServiceOrder.deleted_at.is_(None))
                   .filter(ServiceOrder.pickup_datetime >= datetime.combine(today, datetime.min.time()))
                   .filter(ServiceOrder.pickup_datetime <= datetime.combine(week_end, datetime.max.time()))
                   .filter(ServiceOrder.status.notin_(["cancelado", "finalizado"]))
                   .order_by(ServiceOrder.pickup_datetime.asc())
                   .limit(30).all())

    # ── Pending receivables (OrderPayment, unpaid, ordered by due_date) ──────
    pending_receivables = (OrderPayment.query
                           .join(Order, OrderPayment.order_id == Order.id)
                           .filter(Order.company_id == cid, Order.deleted_at.is_(None))
                           .filter(Order.status.notin_(["cancelado", "excluido"]))
                           .filter(OrderPayment.paid_at.is_(None))
                           .filter(OrderPayment.amount > 0)
                           .order_by(OrderPayment.due_date.asc())
                           .limit(20).all())

    # ── Pending payables (POPayment, unpaid, ordered by due_date) ────────────
    pending_payables = (POPayment.query
                        .join(PurchaseOrder, POPayment.po_id == PurchaseOrder.id)
                        .filter(PurchaseOrder.company_id == cid, PurchaseOrder.deleted_at.is_(None))                        .filter(PurchaseOrder.status.notin_(["cancelado", "excluido"]))                        .filter(POPayment.paid_at.is_(None))
                        .filter(POPayment.amount > 0)
                        .order_by(POPayment.due_date.asc())
                        .limit(20).all())

    # ── Alerts ────────────────────────────────────────────────────────────────
    overdue_recv_count = sum(
        1 for p in pending_receivables
        if p.due_date and p.due_date < today
    )
    overdue_pay_count = sum(
        1 for p in pending_payables
        if p.due_date and p.due_date < today
    )
    expiring_rfq_count = (Quote.query
                          .filter_by(company_id=cid, deleted_at=None)
                          .filter(Quote.status == "pendente")
                          .filter(Quote.valid_until.isnot(None))
                          .filter(Quote.valid_until.between(today, today + timedelta(days=2)))
                          .count())
    expiring_license_count = (Driver.query
                               .filter_by(company_id=cid, is_active=True, deleted_at=None)
                               .filter(Driver.license_expiry.isnot(None))
                               .filter(Driver.license_expiry.between(today, today + timedelta(days=30)))
                               .count())
    alerts = {
        "unassigned_os":       dispatch_summary["pending_count"],
        "overdue_os":          dispatch_summary["overdue_count"],
        "overdue_recv":        overdue_recv_count,
        "overdue_pay":         overdue_pay_count,
        "expiring_rfq":        expiring_rfq_count,
        "expiring_license":    expiring_license_count,
        "total":               (dispatch_summary["pending_count"]
                                + dispatch_summary["overdue_count"]
                                + overdue_recv_count
                                + overdue_pay_count
                                + expiring_rfq_count
                                + expiring_license_count),
    }

    # ── Pending RFQ list (for legacy panel) ──────────────────────────────────
    pending_quotes = (Quote.query
                      .filter_by(company_id=cid, status="pendente", deleted_at=None)
                      .order_by(Quote.created_at.desc()).limit(10).all())

    return render_template(
        "dashboard/index.html",
        # period
        period=period,
        p_start=p_start,
        p_end=p_end,
        # kpi counts
        total_clients=total_clients,
        total_quotes=total_quotes,
        active_so_count=active_so_count,
        open_po_count=open_po_count,
        pending_rfq_count=pending_rfq_count,
        # kpi financials
        so_revenue_month=so_revenue,
        po_cost_month=po_cost,
        margin_month=margin_val,
        margin_pct=margin_pct,
        delta_revenue=delta_revenue,
        delta_pct=delta_pct,
        # chart
        chart_data_json=chart_data_json,
        # pipeline
        funnel_sent_count=funnel_sent_count,
        funnel_sent_val=funnel_sent_val,
        funnel_appr_count=funnel_appr_count,
        funnel_appr_val=funnel_appr_val,
        funnel_so_count=funnel_so_count,
        funnel_so_val=funnel_so_val,
        funnel_closed_count=funnel_closed_count,
        funnel_closed_val=funnel_closed_val,
        conversion_rate=conversion_rate,
        # dispatch
        dispatch_summary=dispatch_summary,
        # upcoming os
        upcoming_os=upcoming_os,
        # receivables / payables
        pending_receivables=pending_receivables,
        pending_payables=pending_payables,
        # alerts
        alerts=alerts,
        # legacy
        pending_quotes=pending_quotes,
        today=today,
    )


@dashboard_bp.route("/settings", methods=["GET", "POST"])
@login_required
@require_permission("settings.manage")
def settings():
    company = Company.query.get(current_user.company_id)
    if request.method == "POST":
        company.name     = (request.form.get("name", "") or company.name).strip() or company.name
        company.document = (request.form.get("document", "") or "").strip()
        company.email    = (request.form.get("email",   "") or "").strip()
        company.phone    = (request.form.get("phone",   "") or "").strip()
        company.address  = (request.form.get("address", "") or "").strip()

        # Logo: prefer file upload, fall back to URL field
        logo_file = request.files.get("logo_file")
        if logo_file and logo_file.filename:
            ext       = os.path.splitext(logo_file.filename)[1].lower()
            allowed   = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
            if ext not in allowed:
                flash("Formato de imagem não suportado. Use PNG, JPG, GIF, WEBP ou SVG.", "danger")
                return redirect(url_for("dashboard.settings"))
            filename  = f"logo_{company.id}_{uuid.uuid4().hex[:8]}{ext}"
            upload_dir = current_app.config["UPLOAD_FOLDER"]
            os.makedirs(upload_dir, exist_ok=True)
            logo_file.save(os.path.join(upload_dir, filename))
            company.logo_url = f"/uploads/{filename}"
        else:
            logo_url = (request.form.get("logo_url", "") or "").strip()
            company.logo_url = logo_url if logo_url else company.logo_url

        db.session.commit()
        flash("Configurações salvas.", "success")
        return redirect(url_for("dashboard.settings"))
    s = (company.settings or {}) if company else {}
    nf_rate   = float(s.get("nf_rate",   current_app.config.get("NF_RATE",   0.10)))
    card_rate = float(s.get("card_rate", current_app.config.get("CARD_RATE", 0.065)))
    return render_template("dashboard/settings.html", company=company,
                           nf_rate=nf_rate, card_rate=card_rate)


@dashboard_bp.route("/settings/reset-transactional", methods=["POST"])
@login_required
@require_permission("settings.manage")
def reset_transactional():
    """Apaga somente SO, PO e Orçamentos. Mantém cadastros base.

    Requer re-autenticação por senha (confirmação explícita do admin).
    """
    if not _confirm_password_and_audit("Reset Transacional (Quotes, Orders, POs)"):
        return redirect(url_for("dashboard.settings"))
    TABLES = [
        "po_items", "po_payments", "purchase_orders",
        "order_items", "order_payments", "orders",
        "quote_inclusions", "quote_items", "quotes",
    ]
    totals = {}
    with db.engine.connect() as conn:
        conn.execute(db.text("PRAGMA foreign_keys = OFF"))
        for table in TABLES:
            result = conn.execute(db.text(f"DELETE FROM {table}"))
            totals[table] = result.rowcount
        conn.execute(db.text("PRAGMA foreign_keys = ON"))
        conn.commit()
    total = sum(totals.values())
    flash(f"Dados transacionais removidos: {total} registro(s) apagado(s). Cadastros base preservados.", "warning")
    return redirect(url_for("dashboard.settings"))


@dashboard_bp.route("/settings/reset-financial", methods=["POST"])
@login_required
@require_permission("settings.manage")
def reset_financial():
    """Apaga somente os registros financeiros. Preserva tudo mais.

    Requer re-autenticação por senha (confirmação explícita do admin).
    """
    if not _confirm_password_and_audit("Reset Financeiro (Registros financeiros)"):
        return redirect(url_for("dashboard.settings"))
    TABLES = [
        "supplier_payments",
        "operation_costs",
        "revenue_entries",
        "financial_entries",
        "financial_records",
        "accounts_receivable",
    ]
    totals = {}
    with db.engine.connect() as conn:
        conn.execute(db.text("PRAGMA foreign_keys = OFF"))
        for table in TABLES:
            result = conn.execute(db.text(f"DELETE FROM {table}"))
            totals[table] = result.rowcount
        conn.execute(db.text("PRAGMA foreign_keys = ON"))
        conn.commit()
    total = sum(totals.values())
    flash(f"Dados financeiros removidos: {total} registro(s) apagado(s).", "warning")
    return redirect(url_for("dashboard.settings"))


@dashboard_bp.route("/settings/reset-all", methods=["POST"])
@login_required
@require_permission("settings.manage")
def reset_all():
    """Apaga TODOS os dados transacionais, financeiros e de despacho.
    Preserva apenas: usuários, empresa, clientes, fornecedores,
    motoristas, veículos, serviços e tabelas de preço.

    Requer re-autenticação por senha (confirmação explícita do admin).
    """
    if not _confirm_password_and_audit("Reset COMPLETO (Todos os dados transacionais + financeiros + auditoria)"):
        return redirect(url_for("dashboard.settings"))
    TABLES = [
        # Filhos de service_orders
        "supplier_payments",
        "operation_costs",
        "revenue_entries",
        "financial_entries",
        "service_order_events",
        "service_order_assignments",
        # Service orders
        "service_orders",
        # PO
        "po_items", "po_payments", "purchase_orders",
        # SO (orders)
        "order_items", "order_payments", "orders",
        # Orçamentos
        "quote_inclusions", "quote_items", "quotes",
        # Financeiro restante
        "financial_records",
        "accounts_receivable",
        # Auditoria
        "audit_logs",
    ]
    totals = {}
    with db.engine.connect() as conn:
        conn.execute(db.text("PRAGMA foreign_keys = OFF"))
        for table in TABLES:
            result = conn.execute(db.text(f"DELETE FROM {table}"))
            totals[table] = result.rowcount
        conn.execute(db.text("PRAGMA foreign_keys = ON"))
        conn.commit()
    total = sum(totals.values())
    flash(f"Sistema zerado: {total} registro(s) removido(s). Cadastros base preservados.", "danger")
    return redirect(url_for("dashboard.settings"))


@dashboard_bp.route("/settings/rates", methods=["POST"])
@login_required
@require_permission("settings.manage")
def save_rates():
    company = Company.query.get(current_user.company_id)
    try:
        nf   = float(request.form.get("nf_rate",   "0.10").replace(",", "."))
        card = float(request.form.get("card_rate", "0.065").replace(",", "."))
        if not (0 <= nf <= 1 and 0 <= card <= 1):
            raise ValueError
    except ValueError:
        flash("Valores inválidos. Use decimais entre 0 e 1.", "danger")
        return redirect(url_for("dashboard.settings"))
    s = dict(company.settings or {})
    s["nf_rate"]   = nf
    s["card_rate"] = card
    company.settings = s
    db.session.commit()
    flash("Taxas atualizadas.", "success")
    return redirect(url_for("dashboard.settings"))
