"""Correção AUTORIZADA das datas dos FRs 8 e 12 (Etapa 6E).

paid_date: 2026-05-29 → 2026-06-02 (data efetiva da baixa da parcela).

Guardas: registros existem, ativos, paid_date atual exatamente 2026-05-29,
parcela correspondente paga em 02/06. Transação ÚNICA para os dois registros
(falha em qualquer um → rollback total). Nenhum outro campo é tocado.

Uso:
    python tools/fix_dates_etapa6e.py [--user-id 1]
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.financial import FinancialRecord  # noqa: E402
from app.utils.audit import log_activity  # noqa: E402

FIX_IDS = [8, 12]
OLD_DATE = date(2026, 5, 29)
NEW_DATE = date(2026, 6, 2)
MOTIVO = "Correção da data do movimento de caixa para coincidir com a data efetiva da baixa da parcela."


class DateFixBlocked(Exception):
    pass


def fix_paid_dates(user_id: int) -> list:
    """Corrige paid_date dos FRs 8 e 12 em UMA transação."""
    results = []
    for fid in FIX_IDS:
        fr = FinancialRecord.query.get(fid)
        if fr is None:
            raise DateFixBlocked(f"FR {fid} inexistente")
        if fr.deleted_at is not None:
            raise DateFixBlocked(f"FR {fid} está soft-deletado")
        if fr.paid_date != OLD_DATE:
            raise DateFixBlocked(f"FR {fid} paid_date atual é {fr.paid_date}, esperado {OLD_DATE}")
        # confirma que a parcela foi paga efetivamente em 02/06
        pid = int(fr.reference.split(":")[1])
        from app.models.order import OrderPayment
        pmt = db.session.get(OrderPayment, pid)
        if pmt is None or not pmt.paid_at or pmt.paid_at.date() != NEW_DATE:
            raise DateFixBlocked(
                f"FR {fid}: parcela {pid} não foi baixada em {NEW_DATE} "
                f"(paid_at={getattr(pmt, 'paid_at', None)})")
        results.append({"id": fid, "reference": fr.reference, "amount": fr.amount,
                        "paid_at_parcela": str(pmt.paid_at)})

    # Aplica as duas alterações antes de qualquer commit (transação única)
    for fid in FIX_IDS:
        fr = FinancialRecord.query.get(fid)
        fr.paid_date = NEW_DATE

    for r in results:
        log_activity("financial", r["id"], FinancialRecord.query.get(r["id"]).company_id,
                     f"CORREÇÃO DE DATA (Etapa 6E) ref={r['reference']} valor={r['amount']:.2f} "
                     f"campo=paid_date anterior={OLD_DATE} novo={NEW_DATE} — {MOTIVO}",
                     user_id)

    db.session.commit()
    return results


def main():
    parser = argparse.ArgumentParser(description="Correção das datas dos FRs 8 e 12 (Etapa 6E)")
    parser.add_argument("--user-id", type=int, default=1)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        try:
            results = fix_paid_dates(args.user_id)
        except DateFixBlocked as e:
            db.session.rollback()
            print(f"[BLOQUEADO] {e} — nada foi alterado.")
            sys.exit(3)
        except Exception:
            db.session.rollback()
            print("[ERRO] Falha inesperada — rollback executado, nada foi alterado.")
            raise
        for r in results:
            print(f"[OK] FR {r['id']} ({r['reference']}, R$ {r['amount']:.2f}): "
                  f"paid_date {OLD_DATE} -> {NEW_DATE} | parcela paga em {r['paid_at_parcela']}")
        print("AUDITORIA REGISTRADA PARA OS 2 REGISTROS.")


if __name__ == "__main__":
    main()
