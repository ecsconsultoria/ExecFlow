"""Restauração CONTROLADA de UM FinancialRecord soft-deletado (Etapa 6).

Uso:
    python tools/restore_financial_record.py <record_id> [--user-id 1]

Registro a registro — NUNCA em lote. Só restaura quando TODAS as guardas
passam (parcela existe e está paga, valor coincide, sem duplicata ativa).
Preserva id, valor, datas, status, reference e company. Auditoria registrada.

FASE B da Etapa 6: usar somente para registros classificados como
RESTAURAÇÃO SEGURA (análise em docs/RELATORIO_ETAPA6.md).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.services.financial_service import restore_and_audit, RestorationBlocked  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Restaura UM FinancialRecord soft-deletado")
    parser.add_argument("record_id", type=int)
    parser.add_argument("--user-id", type=int, default=1, help="usuário da auditoria")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        # company é a do próprio registro (preservada, nunca alterada)
        from app.models.financial import FinancialRecord
        fr = FinancialRecord.query.get(args.record_id)
        if fr is None:
            print(f"[ERRO] FinancialRecord {args.record_id} não existe.")
            sys.exit(2)
        try:
            restored = restore_and_audit(args.record_id, fr.company_id, args.user_id)
            print(f"[OK] FR {restored.id} restaurado — ref={restored.reference} "
                  f"tipo={restored.type} valor={restored.amount:.2f} status={restored.status}")
        except RestorationBlocked as e:
            db.session.rollback()
            print(f"[BLOQUEADO] FR {args.record_id}: {e} — nada foi alterado.")
            sys.exit(3)
        except Exception:
            db.session.rollback()
            print(f"[ERRO] Falha na restauração do FR {args.record_id} — rollback executado.")
            raise


if __name__ == "__main__":
    main()
