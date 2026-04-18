import sqlite3

def extract_for_ai(db_path="db.sqlite", output_file="ai_context.txt"):
    print("Step 1: Connecting to the database...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()

    print("Step 2: Running the Master Extraction...")
    query = """
        SELECT 
            c.Name AS CompanyName,
            fg.SKU AS FinishedGoodSKU,
            rm.SKU AS RawMaterialSKU,
            GROUP_CONCAT(COALESCE(s.Name, 'UNKNOWN_SUPPLIER'), ', ') AS Suppliers
        FROM Company c
        JOIN Product fg ON c.Id = fg.CompanyId 
        JOIN BOM b ON fg.Id = b.ProducedProductId
        JOIN BOM_Component bc ON b.Id = bc.BOMId
        JOIN Product rm ON bc.ConsumedProductId = rm.Id
        LEFT JOIN Supplier_Product sp ON rm.Id = sp.ProductId
        LEFT JOIN Supplier s ON sp.SupplierId = s.Id
        WHERE fg.Type = 'finished-good' AND rm.Type = 'raw-material'
        GROUP BY c.Name, fg.SKU, rm.SKU;
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    print("Step 3: Grouping data into Semantic BOMs...")
    
    # Dictionary to hold the grouped data: {(Company, FinishedGood): [List of Ingredients]}
    products = {}
    
    for row in rows:
        company = row['CompanyName']
        fg = row['FinishedGoodSKU']
        rm = row['RawMaterialSKU']
        suppliers = row['Suppliers']
        
        key = (company, fg)
        if key not in products:
            products[key] = []
            
        # Format the ingredient line
        products[key].append(f"    - {rm} (Approved Suppliers: [{suppliers}])")
        
    print("Step 4: Writing to file...")
    
    ai_facts = []
    for (company, fg), ingredients in products.items():
        # Build the compressed block
        block = f"Company: '{company}' | Finished Good: '{fg}'\nIngredients:\n" + "\n".join(ingredients)
        ai_facts.append(block)
        
    with open(output_file, 'w', encoding='utf-8') as f:
        # Separate each product block with a double newline for clean AI reading
        f.write("\n\n".join(ai_facts))
        
    print(f"Success! Compressed down to {len(ai_facts)} unique product profiles.")
    
    conn.close()

if __name__ == "__main__":
    extract_for_ai()