"""Cancelamento CONTROLADO do FR45 (Etapa 7E — autorização expressa).

Altera SOMENTE FinancialRecord.status: pendente -> cancelado.
SEM delete físico, SEM mudança de valor/datas/vínculos/company.
Transação única com rollback em falha; auditoria registrada.

Uso:
    python tools/cancel_fr45_etapa7e.py [--user-id 1]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.financial import FinancialRecord  # noqa: E402
from app.utils.audit import log_activity  # noqa: E402

FR_ID = 45
MOTIVO = ("Cancelamento autorizado após investigação da Etapa 7D, que não encontrou "
          "evidência de origem, vínculo ou obrigação financeira correspondente.")


class CancelBlocked(Exception):
    pass


def cancel_fr45(user_id: int) -> dict:
    fr = FinancialRecord.query.get(FR_ID)
    if fr is None:
        raise CancelBlocked("FR 45 inexistente")
    if fr.deleted_at is not None:
        raise CancelBlocked("FR 45 está soft-deletado")
    if fr.status != "pendente":
        raise CancelBlocked(f"FR 45 já está com status '{fr.status}' (esperado pendente)")

    before = fr.status
    fr.status = "cancelado"
    log_activity("financial", fr.id, fr.company_id,
                 f"CANCELAMENTO (Etapa 7E) FR45 status anterior={before} "
                 f"novo={fr.status} valor={fr.amount:.2f} reference={fr.reference or '-'} "
                 f"— {MOTIVO}", user_id)
    db.session.commit()
    return {"id": fr.id, "before": before, "after": fr.status, "amount": fr.amount,
            "description": fr.description, "company_id": fr.company_id}


def main():
    parser = argparse.ArgumentParser(description="Cancelamento controlado do FR45 (Etapa 7E)")
    parser.add_argument("--user-id", type=int, default=1)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        try:
            r = cancel_fr45(args.user_id)
        except CancelBlocked as e:
            db.session.rollback()
            print(f"[BLOQUEADO] {e} — nada foi alterado.")
            sys.exit(3)
        except Exception:
            db.session.rollback()
            print("[ERRO] Falha inesperada — rollback executado, nada foi alterado.")
            raise
        print(f"[OK] FR {r['id']}: status {r['before']} -> {r['after']} | "
              f"valor R$ {r['amount']:.2f} | '{r['description']}' | preservado (sem DELETE).")
        print("AUDITORIA REGISTRADA.")


if __name__ == "__main__":
    main()
