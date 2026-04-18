"""
Compliance Checker -- cross-references product requirements with supplier data.
"""

from dataclasses import dataclass
from typing import List
import logging

logger = logging.getLogger(__name__)

@dataclass
class ComplianceCheck:
    requirement: str
    status: str       # "PASS", "FAIL", "UNKNOWN"
    evidence: str
    source_url: str

@dataclass 
class ComplianceResult:
    product_id: int
    ingredient_group_id: int
    proposed_supplier_id: int
    checks: List[ComplianceCheck]
    all_passed: bool
    blocking_issues: List[str]
    warnings: List[str]

def check_compliance(
    product_id: int, 
    ingredient_group_id: int, 
    proposed_supplier_id: int,
    required_certs: List[str],
    supplier_certs: List[str],
    supplier_website: str
) -> ComplianceResult:
    """
    Validates if a proposed supplier meets the compliance requirements of the finished good.
    """
    checks = []
    blocking_issues = []
    warnings = []
    
    supplier_certs_lower = [c.lower() for c in supplier_certs]
    
    for req in required_certs:
        # Match requirement to supplier certifications
        match = any(req.lower() in sc or sc in req.lower() for sc in supplier_certs_lower)
        
        if match:
            checks.append(ComplianceCheck(
                requirement=req,
                status="PASS",
                evidence=f"Supplier holds {req} certification.",
                source_url=supplier_website
            ))
        else:
            checks.append(ComplianceCheck(
                requirement=req,
                status="UNKNOWN",
                evidence=f"Supplier certification {req} not found in gathered data.",
                source_url=supplier_website
            ))
            warnings.append(f"Missing explicit proof for {req} certification.")
            
    all_passed = len(warnings) == 0 and len(blocking_issues) == 0
    
    return ComplianceResult(
        product_id=product_id,
        ingredient_group_id=ingredient_group_id,
        proposed_supplier_id=proposed_supplier_id,
        checks=checks,
        all_passed=all_passed,
        blocking_issues=blocking_issues,
        warnings=warnings
    )
