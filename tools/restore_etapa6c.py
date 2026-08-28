"""Restauração CONTROLADA dos 21 FinancialRecords do Grupo A (Etapa 6C).

Autorização expressa do usuário (Etapa 6C):
  * Restaurar SOMENTE os IDs da allowlist (21 registros do Grupo A).
  * NÃO restaurar os 6 proibidos (7, 31, 32, 34, 43, 44).
  * ID 5: restaurar E corrigir status pendente → pago (autorizado).
  * Uma transação POR REGISTRO; guardas individuais (parcela paga, valor,
    sem duplicata ativa); preserva ID/reference/valor/datas/company.
  * Auditoria por registro com status antes/depois e motivo.

Uso:
    python tools/restore_etapa6c.py [--user-id 1]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.financial import FinancialRecord  # noqa: E402
from app.services.financial_service import restore_financial_record, RestorationBlocked  # noqa: E402
from app.utils.audit import log_activity  # noqa: E402

# Allowlist EXPLÍCITA da Etapa 6C (Grupo A — autorizado). Nunca "todos".
ALLOWED_IDS = [1, 2, 3, 5, 6, 8, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27]
FORBIDDEN_IDS = [7, 31, 32, 34, 43, 44]
ID5 = 5


def restore_records(ids, correct_status_ids, user_id: int) -> list:
    """Restaura registros um a um; retorna lista de resultados."""
    results = []
    for fid in ids:
        try:
            fr = FinancialRecord.query.get(fid)
            if fr is None:
                results.append({"id": fid, "ok": False, "err": "registro inexistente"})
                continue
            if fr.deleted_at is None:
                results.append({"id": fid, "ok": False, "err": "já estava ativo (sem ação)"})
                continue
            # Guardas: parcela existe/paga, valor coincide, sem duplicata ativa.
            restore_financial_record(fid, fr.company_id)
            status_before = fr.status
            note = "restaurado (Grupo A, Etapa 6C)"
            if fid in correct_status_ids and fr.status == "pendente":
                fr.status = "pago"
                note = "status corrigido de pendente para pago por autorização explícita na Etapa 6C"
            log_activity("financial", fr.id, fr.company_id,
                         f"FR RESTAURADO (Etapa 6C) ref={fr.reference} tipo={fr.type} "
                         f"valor={fr.amount:.2f} status_antes={status_before} "
                         f"status_depois={fr.status} — {note}", user_id)
            db.session.commit()  # uma transação por registro
            results.append({"id": fid, "ok": True, "ref": fr.reference, "type": fr.type,
                            "amount": fr.amount, "before": status_before,
                            "after": fr.status, "note": note})
        except RestorationBlocked as e:
            db.session.rollback()  # rollback daquele registro; segue para o próximo
            results.append({"id": fid, "ok": False, "err": str(e)})
        except Exception:
            db.session.rollback()
            raise  # falha inesperada: interrompe tudo (nada parcial fica no banco)
    return results


def main():
    parser = argparse.ArgumentParser(description="Restauração controlada Etapa 6C (21 FRs)")
    parser.add_argument("--user-id", type=int, default=1)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        results = restore_records(ALLOWED_IDS, {ID5}, args.user_id)

        ok = [r for r in results if r["ok"]]
        failed = [r for r in results if not r["ok"]]
        print(f"{'ID':>4} {'reference':<18} {'tipo':<8} {'valor':>12} {'antes':<9} {'depois':<9} {'obs'}")
        for r in ok:
            print(f"{r['id']:>4} {r['ref']:<18} {r['type']:<8} {r['amount']:>12,.2f} "
                  f"{r['before']:<9} {r['after']:<9} {r['note']}")
        for r in failed:
            print(f"{r['id']:>4} FALHOU/BLOQUEADO: {r['err']}")
        print(f"\nRESTAURADOS: {len(ok)} | BLOQUEADOS: {len(failed)} | "
              f"TOTAL VALOR: R$ {sum(r['amount'] for r in ok):,.2f}")

        # Confirma que os 6 proibidos continuam deletados
        still_deleted = [fid for fid in FORBIDDEN_IDS
                         if FinancialRecord.query.get(fid) is not None
                         and FinancialRecord.query.get(fid).deleted_at is not None]
        active_forbidden = [fid for fid in FORBIDDEN_IDS
                            if FinancialRecord.query.get(fid) is not None
                            and FinancialRecord.query.get(fid).deleted_at is None]
        print(f"PROIBIDOS ainda deletados: {sorted(still_deleted)} | ativos indevidos: {active_forbidden}")

        if failed or active_forbidden:
            sys.exit(3)


if __name__ == "__main__":
    main()
