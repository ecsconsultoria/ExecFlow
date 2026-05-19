"""DispatchService — consultas operacionais para o centro de despacho.

Métodos focados em performance para o dashboard de dispatch.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import func, and_

from ..extensions import db
from ..models import ServiceOrder


def get_today(company_id: int, ref_date: date = None) -> list:
    """Retorna todas as OS com pickup no dia, ordenadas por horário."""
    if ref_date is None:
        from ..utils import now_br
        ref_date = now_br().date()

    day_start = datetime.combine(ref_date, datetime.min.time())
    day_end   = datetime.combine(ref_date, datetime.max.time())

    return (ServiceOrder.query
            .filter_by(company_id=company_id)
            .filter(ServiceOrder.deleted_at.is_(None))
            .filter(ServiceOrder.pickup_datetime.between(day_start, day_end))
            .filter(ServiceOrder.status.notin_(["cancelado", "finalizado"]))
            .order_by(ServiceOrder.pickup_datetime.asc())
            .all())


def get_pending_assignment(company_id: int) -> list:
    """OS criadas ou agendadas ainda sem motorista/fornecedor atribuído."""
    return (ServiceOrder.query
            .filter_by(company_id=company_id)
            .filter(ServiceOrder.deleted_at.is_(None))
            .filter(ServiceOrder.status.in_(["criado", "agendado"]))
            .filter(ServiceOrder.assigned_driver_id.is_(None))
            .filter(ServiceOrder.supplier_id.is_(None))
            .order_by(ServiceOrder.pickup_datetime.asc())
            .all())


def get_in_progress(company_id: int) -> list:
    """OS com status em_execucao."""
    return (ServiceOrder.query
            .filter_by(company_id=company_id)
            .filter(ServiceOrder.deleted_at.is_(None))
            .filter_by(status="em_execucao")
            .order_by(ServiceOrder.pickup_datetime.asc())
            .all())


def get_overdue(company_id: int) -> list:
    """OS com pickup no passado que ainda não foram finalizadas ou canceladas."""
    from ..utils import now_br
    now = now_br()
    return (ServiceOrder.query
            .filter_by(company_id=company_id)
            .filter(ServiceOrder.deleted_at.is_(None))
            .filter(ServiceOrder.pickup_datetime < now)
            .filter(ServiceOrder.status.notin_(["finalizado", "cancelado"]))
            .order_by(ServiceOrder.pickup_datetime.asc())
            .all())


def get_summary(company_id: int, ref_date: date = None) -> dict:
    """Resumo do dia para exibição no dashboard de dispatch."""
    if ref_date is None:
        from ..utils import now_br
        ref_date = now_br().date()

    today_os = get_today(company_id, ref_date)
    return {
        "date":          ref_date,
        "today_count":   len(today_os),
        "today_list":    today_os,
        "pending":       get_pending_assignment(company_id),
        "in_progress":   get_in_progress(company_id),
        "overdue":       get_overdue(company_id),
        "pending_count": len(get_pending_assignment(company_id)),
        "overdue_count": len(get_overdue(company_id)),
    }
