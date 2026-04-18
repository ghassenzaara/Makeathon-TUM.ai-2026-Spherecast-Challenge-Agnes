"""
Mock Phase 2 Data Generator

Since the OpenAI API hit rate limits/exhausted credits, this script generates
plausible mock enrichment data for the remaining iHerb products, suppliers,
and finished goods so we can proceed to Phase 3 and Phase 4.
"""

import asyncio
import json
import logging
from typing import Optional

from backend.db.queries import get_all_finished_goods, get_all_suppliers
from backend.phase1_extraction.sku_parser import parse_sku
from backend.phase2_enrichment.enrichment_store import (
    cache_get,
    cache_set,
    store_product_scrape,
    store_supplier_info,
    store_compliance_requirements,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def mock_iherb():
    finished_goods = get_all_finished_goods()
    iherb_products = [
        p for p in finished_goods 
        if parse_sku(p["SKU"]).retailer == "iherb" and parse_sku(p["SKU"]).retailer_product_id
    ]
    
    for p in iherb_products:
        parsed = parse_sku(p["SKU"])
        iherb_id = parsed.retailer_product_id
        
        cached = cache_get("iherb", iherb_id)
        if not cached:
            result = {
                "iherb_id": iherb_id,
                "url": f"https://www.iherb.com/pr/p/{iherb_id}",
                "title": f"Mock iHerb Product {iherb_id}",
                "brand": p["CompanyName"],
                "description": "Mock description",
                "certifications": ["Non-GMO", "GMP Certified"] if int(iherb_id) % 2 == 0 else ["Vegan", "USDA Organic"],
                "ingredients_text": "Mock ingredients list",
                "price_usd": 19.99,
                "scrape_success": False,
                "_inference_note": "Mocked due to API limits",
                "_inference_confidence": 30
            }
            cache_set("iherb", iherb_id, result)
            result["product_id"] = p["Id"]
            result["sku"] = p["SKU"]
            store_product_scrape(p["Id"], result, result["url"])
            logger.info(f"Mocked iHerb {iherb_id}")

def mock_suppliers():
    suppliers = get_all_suppliers()
    for s in suppliers:
        supplier_id = s["Id"]
        supplier_name = s["Name"]
        
        cached = cache_get("suppliers", str(supplier_id))
        if not cached:
            result = {
                "supplier_id": supplier_id,
                "name": supplier_name,
                "headquarters": "Mock City, USA",
                "region": "North America",
                "certifications": ["ISO 9001", "GMP", "Kosher"] if supplier_id % 3 == 0 else ["USDA Organic", "Non-GMO Project Verified"],
                "specialties": ["Vitamins", "Minerals"],
                "company_size": "medium",
                "website": f"https://www.{supplier_name.replace(' ', '').lower()}.com",
                "notes": "Mocked supplier info",
                "confidence": 40,
                "source": "mock"
            }
            cache_set("suppliers", str(supplier_id), result)
            store_supplier_info(supplier_id, result, result["website"])
            logger.info(f"Mocked Supplier {supplier_name}")

def mock_compliance():
    finished_goods = get_all_finished_goods()
    for p in finished_goods:
        product_id = p["Id"]
        product_sku = p["SKU"]
        
        cache_key = f"compliance_{product_id}"
        cached = cache_get("compliance", cache_key)
        if not cached:
            result = {
                "product_id": product_id,
                "product_sku": product_sku,
                "company_name": p["CompanyName"],
                "retailer": parse_sku(product_sku).retailer or "unknown",
                "required_certifications": ["Kosher", "GMP"] if product_id % 4 == 0 else ["Non-GMO"],
                "inferred_constraints": ["plant-based"] if product_id % 5 == 0 else [],
                "regulatory_requirements": ["FDA Compliance", "cGMP"],
                "risk_flags": ["Ingredient origin unknown"] if product_id % 7 == 0 else [],
                "confidence": 35,
                "reasoning": "Mocked compliance inference due to API limits",
                "source": "mock"
            }
            cache_set("compliance", cache_key, result)
            store_compliance_requirements(product_id, result)
            logger.info(f"Mocked Compliance {product_sku}")

def main():
    logger.info("Mocking missing Phase 2 data...")
    mock_iherb()
    mock_suppliers()
    mock_compliance()
    logger.info("Done mocking Phase 2 data.")

if __name__ == "__main__":
    main()
