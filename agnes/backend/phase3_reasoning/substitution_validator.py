"""
Substitution Validator -- validates functional equivalence.

For each substitution group, determines whether the clustered ingredient
variants are safely interchangeable. Uses rule-based heuristics across
ingredient-chemistry axes (form, source, hydration, extraction). No LLM
dependency so this is deterministic and cheap.
"""

from dataclasses import dataclass, field
from typing import List, Set
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class SubstitutionValidation:
    group_id: int
    is_valid: bool
    functional_equivalence_score: float       # 0-1
    known_differences: List[str] = field(default_factory=list)
    recommendation: str = ""
    flagged_axes: List[str] = field(default_factory=list)


# Token markers that indicate meaningful differences between variants.
# Each axis: if variants span two+ distinct markers, flag a difference.
_AXES: dict = {
    "hydration": {"anhydrous", "monohydrate", "dihydrate", "trihydrate", "hexahydrate"},
    "source_animal_vs_plant": {"bovine", "porcine", "fish", "marine", "vegetable", "plant", "vegan"},
    "form_salt": {"citrate", "gluconate", "sulfate", "oxide", "carbonate", "chloride",
                   "phosphate", "ascorbate", "acetate", "fumarate", "lactate",
                   "malate", "bisglycinate", "glycinate", "picolinate", "taurate"},
    "extraction": {"extract", "isolate", "concentrate", "powder", "oil"},
    "processing": {"hydrolyzed", "fermented", "raw", "refined", "unrefined",
                    "cold-pressed", "deodorized"},
    "stereochemistry": {"l-", "d-", "dl-", "d,l-"},
    "tocopherol_form": {"d-alpha", "dl-alpha", "mixed-tocopherols", "tocotrienols"},
    "vit_b12_form": {"cyanocobalamin", "methylcobalamin", "hydroxocobalamin", "adenosylcobalamin"},
    "vit_d_form": {"ergocalciferol", "cholecalciferol", "d2", "d3"},
}


def _tokens(name: str) -> Set[str]:
    n = (name or "").lower()
    # split on non-alphanumeric/hyphen so tokens like 'l-ascorbic' survive
    parts = re.split(r"[^a-z0-9\-]+", n)
    toks = {p for p in parts if p}
    # also include two-word slices joined with hyphen (e.g., "cold-pressed")
    toks |= {p for p in parts if "-" in p}
    return toks


def validate_substitution_group(
    group_id: int,
    canonical_name: str,
    member_names: List[str],
) -> SubstitutionValidation:
    """
    Validates if ingredients in a substitution group are interchangeable.
    """
    unique_names = sorted({(n or "").lower() for n in member_names if n})

    if len(unique_names) <= 1:
        return SubstitutionValidation(
            group_id=group_id,
            is_valid=True,
            functional_equivalence_score=1.0,
            known_differences=[],
            recommendation="Identical ingredients -- trivially substitutable.",
            flagged_axes=[],
        )

    all_tokens = {name: _tokens(name) for name in unique_names}

    known_differences: List[str] = []
    flagged_axes: List[str] = []

    for axis, markers in _AXES.items():
        present = set()
        for toks in all_tokens.values():
            matched = toks & markers
            # also check substring presence for multi-word markers
            for m in markers:
                if any(m in t for t in toks):
                    matched.add(m)
            if matched:
                present |= matched
        if len(present) >= 2:
            flagged_axes.append(axis)
            known_differences.append(
                f"{axis.replace('_', ' ')} differs ({', '.join(sorted(present))})"
            )

    # Score: start at 1.0, subtract 0.15 per flagged axis (capped at 0.0)
    score = max(0.0, 1.0 - 0.15 * len(flagged_axes))

    # Conservative thresholds:
    #  >= 0.85 -> valid
    #  0.55-0.84 -> valid-with-review (flagged for confidence scorer to downgrade)
    #  < 0.55 -> invalid
    if score >= 0.85:
        is_valid = True
        recommendation = "Likely safe to substitute."
    elif score >= 0.55:
        is_valid = True
        recommendation = "Substitutable with review: variant differences detected."
    else:
        is_valid = False
        recommendation = "Do not substitute without formulation review."

    return SubstitutionValidation(
        group_id=group_id,
        is_valid=is_valid,
        functional_equivalence_score=round(score, 3),
        known_differences=known_differences,
        recommendation=recommendation,
        flagged_axes=flagged_axes,
    )
