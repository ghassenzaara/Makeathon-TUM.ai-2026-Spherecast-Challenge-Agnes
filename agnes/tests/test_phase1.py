"""
Verification test for Phase 1 — SKU parsing coverage.

Checks that every single SKU in the database can be parsed successfully.
"""

import sys
sys.path.insert(0, ".")

from backend.db.connection import get_cursor
from backend.phase1_extraction.sku_parser import parse_sku


def test_sku_parsing_coverage():
    """Verify every SKU in the database can be parsed."""
    with get_cursor() as cur:
        cur.execute("SELECT SKU, Type FROM Product")
        products = cur.fetchall()

    total = len(products)
    parsed_ok = 0
    failed = []

    for product in products:
        sku = product["SKU"]
        expected_type = product["Type"]
        parsed = parse_sku(sku)

        if parsed.product_type == "unknown":
            failed.append(sku)
        elif parsed.product_type != expected_type:
            failed.append(f"{sku} (expected {expected_type}, got {parsed.product_type})")
        else:
            parsed_ok += 1

    print(f"\n{'='*60}")
    print(f"SKU PARSING COVERAGE TEST")
    print(f"{'='*60}")
    print(f"Total SKUs: {total}")
    print(f"Parsed OK:  {parsed_ok}")
    print(f"Failed:     {len(failed)}")

    if failed:
        print(f"\nFailed SKUs:")
        for f in failed[:20]:
            print(f"  - {f}")
        print(f"\nTEST FAILED")
        return False
    else:
        print(f"\nALL SKUs PARSED SUCCESSFULLY")
        return True


def test_raw_material_ingredient_extraction():
    """Verify all raw material SKUs produce ingredient names."""
    with get_cursor() as cur:
        cur.execute("SELECT SKU FROM Product WHERE Type='raw-material'")
        rm_skus = [r["SKU"] for r in cur.fetchall()]

    total = len(rm_skus)
    with_name = 0
    without_name = []

    for sku in rm_skus:
        parsed = parse_sku(sku)
        if parsed.ingredient_name:
            with_name += 1
        else:
            without_name.append(sku)

    print(f"\n{'='*60}")
    print(f"INGREDIENT EXTRACTION TEST")
    print(f"{'='*60}")
    print(f"Total RM SKUs:     {total}")
    print(f"With ingredients:  {with_name}")
    print(f"Without:           {len(without_name)}")

    if without_name:
        print(f"\nMissing ingredient names:")
        for s in without_name[:20]:
            print(f"  - {s}")
        print(f"\nTEST FAILED")
        return False
    else:
        print(f"\nALL RM SKUs HAVE INGREDIENT NAMES")
        return True


def test_finished_good_retailer_extraction():
    """Verify all finished good SKUs produce retailer info."""
    with get_cursor() as cur:
        cur.execute("SELECT SKU FROM Product WHERE Type='finished-good'")
        fg_skus = [r["SKU"] for r in cur.fetchall()]

    total = len(fg_skus)
    with_retailer = 0
    retailers = {}

    for sku in fg_skus:
        parsed = parse_sku(sku)
        if parsed.retailer:
            with_retailer += 1
            retailers[parsed.retailer] = retailers.get(parsed.retailer, 0) + 1

    print(f"\n{'='*60}")
    print(f"RETAILER EXTRACTION TEST")
    print(f"{'='*60}")
    print(f"Total FG SKUs:    {total}")
    print(f"With retailer:    {with_retailer}")

    if retailers:
        print(f"\nRetailer distribution:")
        for r, count in sorted(retailers.items(), key=lambda x: -x[1]):
            print(f"  {r}: {count}")

    if with_retailer == total:
        print(f"\nALL FG SKUs HAVE RETAILER INFO")
        return True
    else:
        print(f"\nSOME FG SKUs MISSING RETAILER - check 'unknown' types")
        return False


if __name__ == "__main__":
    t1 = test_sku_parsing_coverage()
    t2 = test_raw_material_ingredient_extraction()
    t3 = test_finished_good_retailer_extraction()

    print(f"\n{'='*60}")
    print(f"OVERALL: {'ALL TESTS PASSED' if all([t1, t2, t3]) else 'SOME TESTS FAILED'}")
    print(f"{'='*60}")
