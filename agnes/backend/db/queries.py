"""
SQL query functions for the Agnes database.

All database access goes through these functions to keep SQL
centralised and testable.
"""

from backend.db.connection import get_cursor


# ──────────────────────────────────────────────
# Products
# ──────────────────────────────────────────────

def get_all_raw_materials() -> list[dict]:
    """
    Return all 876 raw material products with company info.

    Returns list of:
        {Id, SKU, CompanyId, Type, CompanyName}
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT p.Id, p.SKU, p.CompanyId, p.Type, c.Name AS CompanyName
            FROM Product p
            JOIN Company c ON p.CompanyId = c.Id
            WHERE p.Type = 'raw-material'
            ORDER BY p.SKU
        """)
        return cur.fetchall()


def get_all_finished_goods() -> list[dict]:
    """
    Return all 149 finished goods with company info.

    Returns list of:
        {Id, SKU, CompanyId, Type, CompanyName}
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT p.Id, p.SKU, p.CompanyId, p.Type, c.Name AS CompanyName
            FROM Product p
            JOIN Company c ON p.CompanyId = c.Id
            WHERE p.Type = 'finished-good'
            ORDER BY p.SKU
        """)
        return cur.fetchall()


def get_bom_for_product(product_id: int) -> list[dict]:
    """
    Return the BOM (bill of materials) for a finished good.

    Returns list of:
        {BOMId, ConsumedProductId, RawMaterialSKU, CompanyId, CompanyName}
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT b.Id AS BOMId, bc.ConsumedProductId,
                   rm.SKU AS RawMaterialSKU, rm.CompanyId,
                   c.Name AS CompanyName
            FROM BOM b
            JOIN BOM_Component bc ON b.Id = bc.BOMId
            JOIN Product rm ON bc.ConsumedProductId = rm.Id
            JOIN Company c ON rm.CompanyId = c.Id
            WHERE b.ProducedProductId = ?
        """, (product_id,))
        return cur.fetchall()


def get_suppliers_for_product(product_id: int) -> list[dict]:
    """
    Return all suppliers that can supply a given product.

    Returns list of:
        {SupplierId, SupplierName, ProductId}
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT sp.SupplierId, s.Name AS SupplierName, sp.ProductId
            FROM Supplier_Product sp
            JOIN Supplier s ON sp.SupplierId = s.Id
            WHERE sp.ProductId = ?
        """, (product_id,))
        return cur.fetchall()


def get_all_suppliers() -> list[dict]:
    """
    Return all 40 suppliers.

    Returns list of:
        {Id, Name}
    """
    with get_cursor() as cur:
        cur.execute("SELECT Id, Name FROM Supplier ORDER BY Name")
        return cur.fetchall()


def get_all_companies() -> list[dict]:
    """
    Return all 61 companies.

    Returns list of:
        {Id, Name}
    """
    with get_cursor() as cur:
        cur.execute("SELECT Id, Name FROM Company ORDER BY Name")
        return cur.fetchall()


def get_bom_components_with_suppliers() -> list[dict]:
    """
    Return all BOM components joined with their supplier options.
    Used to build full substitution group context.

    Returns list of:
        {BOMId, FinishedGoodId, FinishedGoodSKU, FinishedGoodCompany,
         RawMaterialId, RawMaterialSKU, RawMaterialCompanyId, RawMaterialCompany,
         SupplierId, SupplierName}
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                b.Id AS BOMId,
                fg.Id AS FinishedGoodId,
                fg.SKU AS FinishedGoodSKU,
                fg_c.Name AS FinishedGoodCompany,
                rm.Id AS RawMaterialId,
                rm.SKU AS RawMaterialSKU,
                rm.CompanyId AS RawMaterialCompanyId,
                rm_c.Name AS RawMaterialCompany,
                sp.SupplierId,
                s.Name AS SupplierName
            FROM BOM b
            JOIN Product fg ON b.ProducedProductId = fg.Id
            JOIN Company fg_c ON fg.CompanyId = fg_c.Id
            JOIN BOM_Component bc ON b.Id = bc.BOMId
            JOIN Product rm ON bc.ConsumedProductId = rm.Id
            JOIN Company rm_c ON rm.CompanyId = rm_c.Id
            LEFT JOIN Supplier_Product sp ON sp.ProductId = rm.Id
            LEFT JOIN Supplier s ON sp.SupplierId = s.Id
            ORDER BY rm.SKU
        """)
        return cur.fetchall()


# ──────────────────────────────────────────────
# Substitution Groups (Phase 1 output storage)
# ──────────────────────────────────────────────

def create_substitution_tables():
    """Create tables for storing substitution group results."""
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS SubstitutionGroup (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                CanonicalName TEXT NOT NULL,
                CrossCompanyCount INTEGER DEFAULT 0,
                MemberCount INTEGER DEFAULT 0,
                AvgSimilarity REAL DEFAULT 1.0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS SubstitutionGroupMember (
                GroupId INTEGER NOT NULL,
                ProductId INTEGER NOT NULL,
                SKU TEXT NOT NULL,
                CompanyId INTEGER NOT NULL,
                CompanyName TEXT NOT NULL,
                IngredientName TEXT NOT NULL,
                FOREIGN KEY (GroupId) REFERENCES SubstitutionGroup(Id),
                FOREIGN KEY (ProductId) REFERENCES Product(Id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS SubstitutionGroupSupplier (
                GroupId INTEGER NOT NULL,
                SupplierId INTEGER NOT NULL,
                SupplierName TEXT NOT NULL,
                ProductId INTEGER NOT NULL,
                FOREIGN KEY (GroupId) REFERENCES SubstitutionGroup(Id),
                FOREIGN KEY (SupplierId) REFERENCES Supplier(Id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS SubstitutionGroupConsumer (
                GroupId INTEGER NOT NULL,
                FinishedGoodId INTEGER NOT NULL,
                FinishedGoodSKU TEXT NOT NULL,
                FOREIGN KEY (GroupId) REFERENCES SubstitutionGroup(Id),
                FOREIGN KEY (FinishedGoodId) REFERENCES Product(Id)
            )
        """)


def insert_substitution_group(
    canonical_name: str,
    cross_company_count: int,
    member_count: int,
    avg_similarity: float,
) -> int:
    """Insert a substitution group and return its ID."""
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO SubstitutionGroup
                (CanonicalName, CrossCompanyCount, MemberCount, AvgSimilarity)
            VALUES (?, ?, ?, ?)
        """, (canonical_name, cross_company_count, member_count, avg_similarity))
        return cur.lastrowid


def insert_group_members(group_id: int, members: list[dict]):
    """Insert members into a substitution group."""
    with get_cursor() as cur:
        cur.executemany("""
            INSERT INTO SubstitutionGroupMember
                (GroupId, ProductId, SKU, CompanyId, CompanyName, IngredientName)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            (group_id, m["ProductId"], m["SKU"], m["CompanyId"],
             m["CompanyName"], m["IngredientName"])
            for m in members
        ])


def insert_group_suppliers(group_id: int, suppliers: list[dict]):
    """Insert suppliers into a substitution group."""
    with get_cursor() as cur:
        cur.executemany("""
            INSERT INTO SubstitutionGroupSupplier
                (GroupId, SupplierId, SupplierName, ProductId)
            VALUES (?, ?, ?, ?)
        """, [
            (group_id, s["SupplierId"], s["SupplierName"], s["ProductId"])
            for s in suppliers
        ])


def insert_group_consumers(group_id: int, consumers: list[dict]):
    """Insert consuming finished goods into a substitution group."""
    with get_cursor() as cur:
        cur.executemany("""
            INSERT INTO SubstitutionGroupConsumer
                (GroupId, FinishedGoodId, FinishedGoodSKU)
            VALUES (?, ?, ?)
        """, [
            (group_id, c["FinishedGoodId"], c["FinishedGoodSKU"])
            for c in consumers
        ])


def get_all_substitution_groups() -> list[dict]:
    """Return all substitution groups with their metadata."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT Id, CanonicalName, CrossCompanyCount,
                   MemberCount, AvgSimilarity
            FROM SubstitutionGroup
            ORDER BY CrossCompanyCount DESC, MemberCount DESC
        """)
        return cur.fetchall()


def get_substitution_group_detail(group_id: int) -> dict:
    """Return full details for a substitution group."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM SubstitutionGroup WHERE Id = ?", (group_id,)
        )
        group = cur.fetchone()
        if not group:
            return None

        cur.execute(
            "SELECT * FROM SubstitutionGroupMember WHERE GroupId = ?",
            (group_id,),
        )
        group["Members"] = cur.fetchall()

        cur.execute(
            "SELECT * FROM SubstitutionGroupSupplier WHERE GroupId = ?",
            (group_id,),
        )
        group["Suppliers"] = cur.fetchall()

        cur.execute(
            "SELECT * FROM SubstitutionGroupConsumer WHERE GroupId = ?",
            (group_id,),
        )
        group["Consumers"] = cur.fetchall()

        return group


def clear_substitution_tables():
    """Drop and recreate substitution tables (for re-runs)."""
    with get_cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS SubstitutionGroupConsumer")
        cur.execute("DROP TABLE IF EXISTS SubstitutionGroupSupplier")
        cur.execute("DROP TABLE IF EXISTS SubstitutionGroupMember")
        cur.execute("DROP TABLE IF EXISTS SubstitutionGroup")
    create_substitution_tables()
