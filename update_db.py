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
print("Done.")
