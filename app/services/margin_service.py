"""margin_service.py — Central margin calculation for SO↔PO workflow.

Keeps all margin logic in one place so that Order, PurchaseOrder and Dashboard
all read from the same source of truth.
"""

_CANCELLED = frozenset({'cancelado', 'excluido'})


# ─────────────────────────────────────────────────────────────────────────────
# Pure calculation (no DB access)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_order_margin(order):
    """Return (revenue, cost, margin) floats for a given Order (SO).

    * revenue = order.computed_total
    * cost    = sum of non-cancelled PO totals linked to this order
    * margin  = revenue - cost
    """
    revenue = float(order.computed_total or 0.0)
    cost = sum(
        float(po.computed_total or 0.0)
        for po in order.purchase_orders
        if (po.status or '') not in _CANCELLED
    )
    margin = revenue - cost
    return round(revenue, 2), round(cost, 2), round(margin, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Denormalized write-back
# ─────────────────────────────────────────────────────────────────────────────

def recalculate_order(order):
    """Update denormalized margin fields on *order* and flush (no commit).

    Should be called:
      - after order_service.faturar() / fechar()
      - after purchase_order_service.conclude() / faturar() when po.order_id is set
    """
    from ..extensions import db  # local import avoids circular imports

    _revenue, cost, margin = calculate_order_margin(order)
    order.total_po_cost = cost
    order.margin_amount = margin
    db.session.flush()
