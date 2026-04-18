"""
Substitution Validator -- validates functional equivalence.

For each substitution group, determines if members are interchangeable.
Falls back to a heuristic scoring if LLM is unavailable.
"""

from dataclasses import dataclass
from typing import List
import logging

logger = logging.getLogger(__name__)

@dataclass
class SubstitutionValidation:
    group_id: int
    is_valid: bool
    functional_equivalence_score: float   # 0-1
    known_differences: List[str]          # e.g., "source organism differs"
    recommendation: str                   # "safe to substitute" / "review needed"

def validate_substitution_group(group_id: int, canonical_name: str, member_names: List[str]) -> SubstitutionValidation:
    """
    Validates if ingredients in a substitution group are interchangeable.
    Due to API limits, we use a heuristic instead of an LLM.
    """
    unique_names = set([n.lower() for n in member_names])
    
    known_differences = []
    
    # Simple heuristics for differences
    if any("anhydrous" in n for n in unique_names) and any("monohydrate" in n for n in unique_names):
        known_differences.append("Hydration state differs (anhydrous vs monohydrate)")
    
    if any("vegetable" in n for n in unique_names) and any("bovine" in n for n in unique_names):
        known_differences.append("Source differs (vegetable vs bovine)")
        
    score = 1.0 - (0.2 * len(known_differences))
    if len(unique_names) == 1:
        score = 1.0
        
    is_valid = score >= 0.8
    recommendation = "Safe to substitute" if is_valid else "Review needed: potential form differences"
    
    return SubstitutionValidation(
        group_id=group_id,
        is_valid=is_valid,
        functional_equivalence_score=score,
        known_differences=known_differences,
        recommendation=recommendation
    )
