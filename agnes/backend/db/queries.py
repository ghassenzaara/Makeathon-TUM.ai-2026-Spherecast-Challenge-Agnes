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
        cur.execute("DROP TABLE IF EXISTS SubstitutionLink")
    create_substitution_tables()


def create_substitution_group_v2_tables():
    """
    Extended substitution tables with attribute-rich columns.
    Drops + recreates SubstitutionGroup so we can add JSON columns.
    """
    with get_cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS SubstitutionGroup")
        cur.execute("""
            CREATE TABLE SubstitutionGroup (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                CanonicalName TEXT NOT NULL,
                CrossCompanyCount INTEGER DEFAULT 0,
                MemberCount INTEGER DEFAULT 0,
                AvgSimilarity REAL DEFAULT 1.0,
                UnifiedAttributesJson TEXT DEFAULT '{}',
                DivergentAttributesJson TEXT DEFAULT '{}'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS SubstitutionLink (
                FromGroupId INTEGER NOT NULL,
                ToGroupId INTEGER NOT NULL,
                Similarity REAL NOT NULL,
                CaveatsJson TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (FromGroupId, ToGroupId),
                FOREIGN KEY (FromGroupId) REFERENCES SubstitutionGroup(Id),
                FOREIGN KEY (ToGroupId) REFERENCES SubstitutionGroup(Id)
            )
        """)


def insert_substitution_group_v2(
    canonical_name: str,
    cross_company_count: int,
    member_count: int,
    avg_similarity: float,
    unified_json: str = "{}",
    divergent_json: str = "{}",
) -> int:
    """Insert a substitution group (v2, with attribute columns)."""
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO SubstitutionGroup
                (CanonicalName, CrossCompanyCount, MemberCount, AvgSimilarity,
                 UnifiedAttributesJson, DivergentAttributesJson)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (canonical_name, cross_company_count, member_count,
              avg_similarity, unified_json, divergent_json))
        return cur.lastrowid


def insert_substitution_link(
    from_group_id: int,
    to_group_id: int,
    similarity: float,
    caveats_json: str = "[]",
):
    """Insert a cross-group substitution link (functional substitute, not merge)."""
    with get_cursor() as cur:
        cur.execute("""
            INSERT OR REPLACE INTO SubstitutionLink
                (FromGroupId, ToGroupId, Similarity, CaveatsJson)
            VALUES (?, ?, ?, ?)
        """, (from_group_id, to_group_id, similarity, caveats_json))


def get_substitution_links_for_group(group_id: int) -> list[dict]:
    """Return all links touching this group (either direction)."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT FromGroupId, ToGroupId, Similarity, CaveatsJson
            FROM SubstitutionLink
            WHERE FromGroupId = ? OR ToGroupId = ?
        """, (group_id, group_id))
        return cur.fetchall()


# ──────────────────────────────────────────────
# Ingredient cards (attribute-rich ingredients)
# ──────────────────────────────────────────────

def create_ingredient_card_tables():
    """Create tables for structured ingredient cards and their multi-value props."""
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS IngredientCard (
                ProductId INTEGER PRIMARY KEY,
                Substance TEXT,
                Form TEXT,
                Grade TEXT,
                Hydration TEXT,
                SaltOrEster TEXT,
                Source TEXT,
                SourceDetail TEXT,
                Chirality TEXT,
                VitDForm TEXT,
                VitB12Form TEXT,
                TocopherolForm TEXT,
                ExtractedAt TEXT,
                ExtractionMethod TEXT,
                RawIngredientName TEXT,
                FOREIGN KEY (ProductId) REFERENCES Product(Id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS CardCertification (
                ProductId INTEGER NOT NULL,
                Certification TEXT NOT NULL,
                EvidenceId INTEGER,
                PRIMARY KEY (ProductId, Certification),
                FOREIGN KEY (ProductId) REFERENCES Product(Id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS CardAllergen (
                ProductId INTEGER NOT NULL,
                Allergen TEXT NOT NULL,
                EvidenceId INTEGER,
                PRIMARY KEY (ProductId, Allergen),
                FOREIGN KEY (ProductId) REFERENCES Product(Id)
            )
        """)


def clear_ingredient_card_tables():
    with get_cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS CardAllergen")
        cur.execute("DROP TABLE IF EXISTS CardCertification")
        cur.execute("DROP TABLE IF EXISTS IngredientCard")
    create_ingredient_card_tables()


def upsert_ingredient_card(card: dict):
    """Insert or replace an IngredientCard row. Keys: ProductId, Substance, Form, ..."""
    with get_cursor() as cur:
        cur.execute("""
            INSERT OR REPLACE INTO IngredientCard (
                ProductId, Substance, Form, Grade, Hydration, SaltOrEster,
                Source, SourceDetail, Chirality, VitDForm, VitB12Form,
                TocopherolForm, ExtractedAt, ExtractionMethod, RawIngredientName
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            card.get("ProductId"),
            card.get("Substance"),
            card.get("Form"),
            card.get("Grade"),
            card.get("Hydration"),
            card.get("SaltOrEster"),
            card.get("Source"),
            card.get("SourceDetail"),
            card.get("Chirality"),
            card.get("VitDForm"),
            card.get("VitB12Form"),
            card.get("TocopherolForm"),
            card.get("ExtractedAt"),
            card.get("ExtractionMethod"),
            card.get("RawIngredientName"),
        ))


def insert_card_certification(product_id: int, certification: str, evidence_id: int | None = None):
    with get_cursor() as cur:
        cur.execute("""
            INSERT OR REPLACE INTO CardCertification (ProductId, Certification, EvidenceId)
            VALUES (?, ?, ?)
        """, (product_id, certification, evidence_id))


def insert_card_allergen(product_id: int, allergen: str, evidence_id: int | None = None):
    with get_cursor() as cur:
        cur.execute("""
            INSERT OR REPLACE INTO CardAllergen (ProductId, Allergen, EvidenceId)
            VALUES (?, ?, ?)
        """, (product_id, allergen, evidence_id))


def get_ingredient_card(product_id: int) -> dict | None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM IngredientCard WHERE ProductId = ?", (product_id,))
        row = cur.fetchone()
        if not row:
            return None
        cur.execute("SELECT Certification FROM CardCertification WHERE ProductId = ?",
                    (product_id,))
        row["Certifications"] = [r["Certification"] for r in cur.fetchall()]
        cur.execute("SELECT Allergen FROM CardAllergen WHERE ProductId = ?",
                    (product_id,))
        row["Allergens"] = [r["Allergen"] for r in cur.fetchall()]
        return row


def get_all_ingredient_cards() -> list[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM IngredientCard")
        return cur.fetchall()


# ──────────────────────────────────────────────
# Ingredient-level compliance requirements
# ──────────────────────────────────────────────

def create_ingredient_compliance_tables():
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS IngredientComplianceRequirement (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                FinishedGoodId INTEGER NOT NULL,
                RawMaterialId INTEGER NOT NULL,
                Requirement TEXT NOT NULL,
                DerivationType TEXT NOT NULL,
                Confidence REAL NOT NULL DEFAULT 0.5,
                EvidenceId INTEGER,
                CreatedAt TEXT,
                FOREIGN KEY (FinishedGoodId) REFERENCES Product(Id),
                FOREIGN KEY (RawMaterialId) REFERENCES Product(Id)
            )
        """)


def clear_ingredient_compliance_tables():
    with get_cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS IngredientComplianceRequirement")
    create_ingredient_compliance_tables()


def insert_ingredient_compliance_requirement(row: dict) -> int:
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO IngredientComplianceRequirement (
                FinishedGoodId, RawMaterialId, Requirement,
                DerivationType, Confidence, EvidenceId, CreatedAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row["FinishedGoodId"], row["RawMaterialId"], row["Requirement"],
            row["DerivationType"], row["Confidence"],
            row.get("EvidenceId"), row.get("CreatedAt"),
        ))
        return cur.lastrowid


def get_requirements_for_raw_material(fg_id: int, rm_id: int) -> list[dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM IngredientComplianceRequirement
            WHERE FinishedGoodId = ? AND RawMaterialId = ?
        """, (fg_id, rm_id))
        return cur.fetchall()


def get_requirements_for_finished_good(fg_id: int) -> list[dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM IngredientComplianceRequirement
            WHERE FinishedGoodId = ?
        """, (fg_id,))
        return cur.fetchall()


# ──────────────────────────────────────────────
# Contradictions
# ──────────────────────────────────────────────

def create_contradiction_tables():
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Contradiction (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                SubjectType TEXT NOT NULL,
                SubjectId INTEGER NOT NULL,
                Rule TEXT NOT NULL,
                DetailJson TEXT NOT NULL,
                Severity TEXT NOT NULL,
                DetectedAt TEXT NOT NULL
            )
        """)


def clear_contradiction_tables():
    with get_cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS Contradiction")
    create_contradiction_tables()


def insert_contradiction(row: dict) -> int:
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO Contradiction
                (SubjectType, SubjectId, Rule, DetailJson, Severity, DetectedAt)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            row["SubjectType"], row["SubjectId"], row["Rule"],
            row["DetailJson"], row["Severity"], row["DetectedAt"],
        ))
        return cur.lastrowid


def get_all_contradictions() -> list[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM Contradiction ORDER BY DetectedAt DESC")
        return cur.fetchall()


def count_contradictions() -> int:
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM Contradiction")
        return cur.fetchone()["c"]


# ──────────────────────────────────────────────
# Sourcing Proposals (Phase 3 output storage)
# ──────────────────────────────────────────────

def create_proposal_tables():
    """Create tables for Phase 3 sourcing proposals."""
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS SourcingProposal (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                IngredientGroupId INTEGER NOT NULL,
                RecommendedSupplierId INTEGER NOT NULL,
                RecommendedSupplierName TEXT NOT NULL,
                CompaniesConsolidated INTEGER NOT NULL,
                MembersServed INTEGER NOT NULL,
                TotalCompaniesInGroup INTEGER NOT NULL,
                EstimatedSavingsPct REAL NOT NULL,
                ComplianceStatus TEXT NOT NULL,
                RiskFactorsJson TEXT NOT NULL DEFAULT '[]',
                ConfidenceScore REAL NOT NULL DEFAULT 0.0,
                Priority TEXT NOT NULL,
                EvidenceSummary TEXT NOT NULL DEFAULT '',
                VerificationsJson TEXT NOT NULL DEFAULT '{}',
                VerificationPassed INTEGER NOT NULL DEFAULT 0,
                CreatedAt TEXT NOT NULL,
                FOREIGN KEY (IngredientGroupId) REFERENCES SubstitutionGroup(Id),
                FOREIGN KEY (RecommendedSupplierId) REFERENCES Supplier(Id)
            )
        """)


def clear_proposal_tables():
    with get_cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS SourcingProposal")
    create_proposal_tables()


def insert_sourcing_proposal(row: dict) -> int:
    """Insert a single sourcing proposal record."""
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO SourcingProposal (
                IngredientGroupId, RecommendedSupplierId, RecommendedSupplierName,
                CompaniesConsolidated, MembersServed, TotalCompaniesInGroup,
                EstimatedSavingsPct, ComplianceStatus, RiskFactorsJson,
                ConfidenceScore, Priority, EvidenceSummary,
                VerificationsJson, VerificationPassed, CreatedAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["IngredientGroupId"],
            row["RecommendedSupplierId"],
            row["RecommendedSupplierName"],
            row["CompaniesConsolidated"],
            row["MembersServed"],
            row["TotalCompaniesInGroup"],
            row["EstimatedSavingsPct"],
            row["ComplianceStatus"],
            row["RiskFactorsJson"],
            row["ConfidenceScore"],
            row["Priority"],
            row["EvidenceSummary"],
            row["VerificationsJson"],
            row["VerificationPassed"],
            row["CreatedAt"],
        ))
        return cur.lastrowid


def get_all_sourcing_proposals() -> list[dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM SourcingProposal
            ORDER BY
                CASE Priority
                    WHEN 'HIGH' THEN 3
                    WHEN 'MEDIUM' THEN 2
                    WHEN 'LOW' THEN 1
                    ELSE 0
                END DESC,
                ConfidenceScore DESC,
                EstimatedSavingsPct DESC
        """)
        return cur.fetchall()


def get_sourcing_proposal(proposal_id: int) -> dict | None:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM SourcingProposal WHERE Id = ?", (proposal_id,))
        return cur.fetchone()


def get_consumer_finished_goods(group_id: int) -> list[dict]:
    """Finished goods (with company) consuming a substitution group's members."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT
                sgc.FinishedGoodId, sgc.FinishedGoodSKU,
                p.CompanyId, c.Name AS CompanyName
            FROM SubstitutionGroupConsumer sgc
            JOIN Product p  ON p.Id = sgc.FinishedGoodId
            JOIN Company c  ON c.Id = p.CompanyId
            WHERE sgc.GroupId = ?
        """, (group_id,))
        return cur.fetchall()
