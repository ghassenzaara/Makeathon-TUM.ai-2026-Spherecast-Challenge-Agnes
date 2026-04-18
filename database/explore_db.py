import sqlite3

conn = sqlite3.connect('db.sqlite')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("=== TABLES ===")
print(tables)

# Get schema and sample data for each table
for table in tables:
    print(f"\n=== {table} ===")
    cursor.execute(f"PRAGMA table_info({table})")
    cols = cursor.fetchall()
    print("Columns:", [(c[1], c[2]) for c in cols])
    
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"Row count: {count}")
    
    cursor.execute(f"SELECT * FROM {table} LIMIT 3")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

conn.close()
