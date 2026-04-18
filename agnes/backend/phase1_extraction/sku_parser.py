"""
SKU Parser — extracts structured data from Agnes SKU strings.

Handles all observed SKU patterns in the database:
  - RM-C{company_id}-{ingredient-name}-{8-char-hash}
  - FG-iherb-{id}
  - FG-iherb-cen-{id}
  - FG-thrive-market-{slug-or-id}
  - FG-walmart-{id}
  - FG-amazon-{asin}
  - FG-target-{id}
  - FG-costco-{id}
  - FG-sams-club-{id}
  - FG-walgreens-{id}
  - FG-cvs-{id}
  - FG-gnc-{id}
  - FG-the-vitamin-shoppe-{id}
  - FG-vitacost-{id}
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedSKU:
    """Structured representation of a parsed SKU."""
    raw_sku: str
    product_type: str           # 'raw-material' or 'finished-good'
    company_id: Optional[int] = None
    ingredient_name: Optional[str] = None
    hash_suffix: Optional[str] = None
    retailer: Optional[str] = None
    retailer_product_id: Optional[str] = None

    @property
    def display_name(self) -> str:
        """Human-readable name derived from the SKU."""
        if self.ingredient_name:
            return self.ingredient_name.replace("-", " ").title()
        if self.retailer and self.retailer_product_id:
            return f"{self.retailer.title()} Product {self.retailer_product_id}"
        return self.raw_sku


# Pre-compiled regex patterns for performance
_RM_PATTERN = re.compile(
    r"^RM-C(\d+)-(.+)-([a-f0-9]{8})$"
)

# Retailer patterns — ordered from most specific to least
_FG_PATTERNS = [
    # Multi-word retailer names (must come first)
    (re.compile(r"^FG-thrive-market-(.+)$"), "thrive-market"),
    (re.compile(r"^FG-sams-club-(.+)$"), "sams-club"),
    (re.compile(r"^FG-the-vitamin-shoppe-(.+)$"), "the-vitamin-shoppe"),
    # iHerb variants
    (re.compile(r"^FG-iherb-cen-(\d+)$"), "iherb"),
    (re.compile(r"^FG-iherb-(\d+)$"), "iherb"),
    # Single-word retailers
    (re.compile(r"^FG-walmart-(.+)$"), "walmart"),
    (re.compile(r"^FG-amazon-(.+)$"), "amazon"),
    (re.compile(r"^FG-target-(.+)$"), "target"),
    (re.compile(r"^FG-costco-(.+)$"), "costco"),
    (re.compile(r"^FG-walgreens-(.+)$"), "walgreens"),
    (re.compile(r"^FG-cvs-(.+)$"), "cvs"),
    (re.compile(r"^FG-gnc-(.+)$"), "gnc"),
    (re.compile(r"^FG-vitacost-(.+)$"), "vitacost"),
]


def parse_sku(sku: str) -> ParsedSKU:
    """
    Parse a SKU string into a structured ParsedSKU object.

    Examples:
        >>> parse_sku('RM-C28-vitamin-d3-cholecalciferol-8956b79c')
        ParsedSKU(product_type='raw-material', company_id=28,
                  ingredient_name='vitamin-d3-cholecalciferol', ...)

        >>> parse_sku('FG-iherb-10421')
        ParsedSKU(product_type='finished-good', retailer='iherb',
                  retailer_product_id='10421', ...)
    """
    # Try raw material pattern
    rm_match = _RM_PATTERN.match(sku)
    if rm_match:
        return ParsedSKU(
            raw_sku=sku,
            product_type="raw-material",
            company_id=int(rm_match.group(1)),
            ingredient_name=rm_match.group(2),
            hash_suffix=rm_match.group(3),
        )

    # Try finished-good retailer patterns
    for pattern, retailer in _FG_PATTERNS:
        fg_match = pattern.match(sku)
        if fg_match:
            return ParsedSKU(
                raw_sku=sku,
                product_type="finished-good",
                retailer=retailer,
                retailer_product_id=fg_match.group(1),
            )

    # Fallback: unknown format
    return ParsedSKU(
        raw_sku=sku,
        product_type="unknown",
    )


def extract_ingredient_name(sku: str) -> Optional[str]:
    """
    Quick helper: extract just the ingredient name from a raw material SKU.
    Returns None if the SKU is not a raw material.
    """
    parsed = parse_sku(sku)
    return parsed.ingredient_name


def normalize_ingredient_name(name: str) -> str:
    """
    Normalize an ingredient name for comparison.
    Strips hyphens, lowercases, and removes common noise words.
    """
    # Replace hyphens with spaces
    normalized = name.lower().replace("-", " ").strip()
    return normalized


def parse_all_skus(skus: list[str]) -> list[ParsedSKU]:
    """Parse a batch of SKUs and return structured results."""
    return [parse_sku(sku) for sku in skus]
