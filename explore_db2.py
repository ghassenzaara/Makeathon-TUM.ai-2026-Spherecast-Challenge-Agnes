import sqlite3

conn = sqlite3.connect('db.sqlite')
cursor = conn.cursor()

# Get raw material products (not finished goods)
print("=== RAW MATERIALS (sample) ===")
cursor.execute("SELECT * FROM Product WHERE Type='raw-material' LIMIT 10")
for row in cursor.fetchall():
    print(row)

print("\n=== FINISHED GOODS (sample) ===")
cursor.execute("SELECT p.Id, p.SKU, c.Name as Company FROM Product p JOIN Company c ON p.CompanyId = c.Id WHERE p.Type='finished-good' LIMIT 10")
for row in cursor.fetchall():
    print(row)

print("\n=== BOM with Components (sample) ===")
cursor.execute("""
    SELECT b.Id as BOM_Id, fg.SKU as FinishedGood, c.Name as Company, 
           rm.SKU as RawMaterial
    FROM BOM b
    JOIN Product fg ON b.ProducedProductId = fg.Id
    JOIN Company c ON fg.CompanyId = c.Id
    JOIN BOM_Component bc ON b.Id = bc.BOMId
    JOIN Product rm ON bc.ConsumedProductId = rm.Id
    LIMIT 15
""")
for row in cursor.fetchall():
    print(row)

print("\n=== Supplier Products (sample) ===")
cursor.execute("""
    SELECT s.Name as Supplier, p.SKU as Product, p.Type
    FROM Supplier_Product sp
    JOIN Supplier s ON sp.SupplierId = s.Id
    JOIN Product p ON sp.ProductId = p.Id
    LIMIT 15
""")
for row in cursor.fetchall():
    print(row)

# Count stats
print("\n=== STATS ===")
cursor.execute("SELECT COUNT(*) FROM Product WHERE Type='finished-good'")
print(f"Finished goods: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM Product WHERE Type='raw-material'")
print(f"Raw materials: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(DISTINCT CompanyId) FROM Product WHERE Type='finished-good'")
print(f"Companies with finished goods: {cursor.fetchone()[0]}")

# Check for raw materials shared across multiple BOMs
print("\n=== RAW MATERIALS SHARED ACROSS MULTIPLE BOMs (top 15) ===")
cursor.execute("""
    SELECT rm.SKU, COUNT(DISTINCT bc.BOMId) as bom_count
    FROM BOM_Component bc
    JOIN Product rm ON bc.ConsumedProductId = rm.Id
    GROUP BY rm.Id
    HAVING bom_count > 1
    ORDER BY bom_count DESC
    LIMIT 15
""")
for row in cursor.fetchall():
    print(row)

# Raw materials with multiple suppliers
print("\n=== RAW MATERIALS WITH MULTIPLE SUPPLIERS (top 15) ===")
cursor.execute("""
    SELECT p.SKU, COUNT(DISTINCT sp.SupplierId) as supplier_count
    FROM Supplier_Product sp
    JOIN Product p ON sp.ProductId = p.Id
    GROUP BY p.Id
    HAVING supplier_count > 1
    ORDER BY supplier_count DESC
    LIMIT 15
""")
for row in cursor.fetchall():
    print(row)

conn.close()
