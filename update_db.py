import sqlite3

db_path = r"c:\Users\ECS\OneDrive - ECS Consultoria\AI_Projects\App_Orcamentos\App_Orcamentos_V4\instance\erp_v4.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get existing columns
c.execute("PRAGMA table_info(orders)")
existing = {row[1] for row in c.fetchall()}
print("Existing columns:", sorted(existing))

# Add new columns if not present
new_cols = [
    ("emission_date",      "DATE"),
    ("delivery_datetime",  "DATETIME"),
    ("discount_type",      "VARCHAR(5) DEFAULT 'R$'"),
    ("discount_value",     "FLOAT DEFAULT 0"),
    ("freight_amount",     "FLOAT DEFAULT 0"),
    ("other_costs_amount", "FLOAT DEFAULT 0"),
    ("reopened_at",        "DATETIME"),
]

for col, col_type in new_cols:
    if col not in existing:
        sql = f"ALTER TABLE orders ADD COLUMN {col} {col_type}"
        c.execute(sql)
        print(f"Added: {col}")
    else:
        print(f"Already exists: {col}")

conn.commit()
conn.close()

# ── Phase 1: Rename BR- order numbers to SO- ─────────────────────────────────
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM orders WHERE number LIKE 'BR-%'")
br_count = c.fetchone()[0]
if br_count > 0:
    c.execute("UPDATE orders SET number = REPLACE(number, 'BR-', 'SO-') WHERE number LIKE 'BR-%'")
    conn.commit()
    print(f"Renumbered {br_count} order(s): BR- → SO-")
else:
    print("No BR- orders to rename.")
conn.close()

print("Done.")

# ── Phase 2: Service behavior flags + purchase_orders table ──────────────────
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 2a. Flags de comportamento na tabela services
c.execute("PRAGMA table_info(services)")
svc_cols = {row[1] for row in c.fetchall()}
svc_new = [
    ("is_operational",     "BOOLEAN DEFAULT 0"),
    ("requires_route",     "BOOLEAN DEFAULT 0"),
    ("requires_passenger", "BOOLEAN DEFAULT 0"),
    ("requires_vehicle",   "BOOLEAN DEFAULT 0"),
    ("requires_dispatch",  "BOOLEAN DEFAULT 0"),
    ("requires_schedule",  "BOOLEAN DEFAULT 0"),
]
for col, col_type in svc_new:
    if col not in svc_cols:
        c.execute(f"ALTER TABLE services ADD COLUMN {col} {col_type}")
        print(f"services: Added column {col}")
    else:
        print(f"services: Already exists {col}")

# 2b. Tabela purchase_orders (cria se não existir)
c.execute("""
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        number              VARCHAR(50) UNIQUE NOT NULL,
        company_id          INTEGER NOT NULL REFERENCES companies(id),
        created_by          INTEGER REFERENCES users(id),
        service_order_id    INTEGER REFERENCES service_orders(id),
        order_id            INTEGER REFERENCES orders(id),
        quote_id            INTEGER REFERENCES quotes(id),
        supplier_id         INTEGER REFERENCES suppliers(id),
        service_id          INTEGER REFERENCES services(id),
        passenger_name      VARCHAR(200),
        passenger_phone     VARCHAR(50),
        pax_count           INTEGER DEFAULT 1,
        pickup_datetime     DATETIME,
        pickup_location     TEXT,
        dropoff_location    TEXT,
        flight_number       VARCHAR(50),
        vehicle_category_id INTEGER REFERENCES vehicle_categories(id),
        vehicle_description VARCHAR(200),
        driver_name         VARCHAR(200),
        amount              FLOAT DEFAULT 0.0,
        payment_method      VARCHAR(50),
        payment_due_date    DATE,
        paid_at             DATETIME,
        status              VARCHAR(50) DEFAULT 'rascunho',
        notes               TEXT,
        internal_notes      TEXT,
        sent_at             DATETIME,
        approved_at         DATETIME,
        concluded_at        DATETIME,
        cancelled_at        DATETIME,
        created_at          DATETIME,
        updated_at          DATETIME,
        deleted_at          DATETIME
    )
""")
print("purchase_orders: table ensured.")

conn.commit()
conn.close()
print("Phase 2 migration done.")
