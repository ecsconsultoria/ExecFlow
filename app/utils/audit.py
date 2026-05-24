"""utils/audit.py — Helper para registrar ações no log de auditoria."""
from ..extensions import db
from ..models.audit import AuditLog


def log_activity(
    entity: str,
    entity_id: int,
    company_id: int,
    action: str,
    user_id: int | None = None,
) -> None:
    """Registra uma ação no log de auditoria.

    O caller é responsável por chamar db.session.commit() após esta função.
    """
    entry = AuditLog(
        entity=entity,
        entity_id=entity_id,
        company_id=company_id,
        action=action,
        user_id=user_id,
    )
    db.session.add(entry)
