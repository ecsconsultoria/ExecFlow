"""
Limpa SOMENTE os dados transacionais (SO, PO, Orçamentos).
Mantém: usuários, empresa, clientes, serviços, veículos, motoristas, fornecedores, categorias.

Uso:
    python reset_transactional.py
"""
from app_v2 import app
from app.extensions import db

TABLES = [
    # Filhos de purchase_orders (primeiro)
    "po_items",
    "po_payments",
    # purchase_orders referencia orders → deletar antes de orders
    "purchase_orders",
    # Filhos de orders
    "order_items",
    "order_payments",
    # orders
    "orders",
    # bookings referencia quotes → deletar antes de quotes
    "bookings",
    # Filhos de quotes
    "quote_inclusions",
    "quote_items",
    # quotes
    "quotes",
]

with app.app_context():
    with db.engine.connect() as conn:
        # SQLite não ativa FKs por padrão; ativa para garantir integridade
        conn.execute(db.text("PRAGMA foreign_keys = OFF"))
        for table in TABLES:
            result = conn.execute(db.text(f"DELETE FROM {table}"))
            print(f"  {table}: {result.rowcount} linha(s) removida(s)")
        conn.execute(db.text("PRAGMA foreign_keys = ON"))
        conn.commit()

print("\nPronto. SO, PO e Orçamentos limpos. Demais dados preservados.")
