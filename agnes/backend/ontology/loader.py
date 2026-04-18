"""
Ontology loader -- single cached entry point for all ontology files.

Call sites:
    from backend.ontology import get_ontologies
    onts = get_ontologies()
    onts.substances.canonicalize("vitamin-c")   # -> "ascorbic-acid"
    onts.certifications.canonicalize("USDA Organic")  # -> "organic"
    onts.attributes.extract_tokens("RM-C07-vitamin-d3-cholecalciferol-abc123")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from backend.config import ONTOLOGY_DIR


# ──────────────────────────────────────────────
# Ontology dataclasses
# ──────────────────────────────────────────────

@dataclass
class SubstanceOntology:
    """Canonical substance names + aliases."""
    raw: dict
    _alias_to_canonical: dict[str, str] = field(default_factory=dict)
    _canonical_merge: dict[str, str] = field(default_factory=dict)
    _categories: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        for canonical, spec in self.raw.items():
            if canonical.startswith("_"):
                continue
            self._alias_to_canonical[canonical] = canonical
            for alias in spec.get("aliases", []) or []:
                self._alias_to_canonical[alias.lower()] = canonical
            if spec.get("merge_with"):
                self._canonical_merge[canonical] = spec["merge_with"]
            self._categories[canonical] = spec.get("category", "unknown")

    def canonicalize(self, name: str) -> str | None:
        """Return canonical substance for a raw or aliased name, or None."""
        if not name:
            return None
        key = name.lower().strip()
        hit = self._alias_to_canonical.get(key)
        if hit and hit in self._canonical_merge:
            return self._canonical_merge[hit]
        return hit

    def category_of(self, canonical: str) -> str:
        return self._categories.get(canonical, "unknown")

    def canonicals(self) -> list[str]:
        return [k for k in self.raw.keys() if not k.startswith("_")]


@dataclass
class CertificationOntology:
    """Canonical certifications + synonym groups."""
    raw: dict
    _synonym_to_canonical: dict[str, str] = field(default_factory=dict)
    _blocking: set[str] = field(default_factory=set)

    def __post_init__(self):
        for canonical, spec in self.raw.items():
            if canonical.startswith("_"):
                continue
            self._synonym_to_canonical[canonical.lower()] = canonical
            for syn in spec.get("synonyms", []) or []:
                self._synonym_to_canonical[syn.lower()] = canonical
            if spec.get("blocking"):
                self._blocking.add(canonical)

    def canonicalize(self, raw_cert: str) -> str | None:
        """Normalize any label to its canonical cert. Tries exact then word-boundary."""
        if not raw_cert:
            return None
        norm = re.sub(r"\s+", " ", raw_cert.lower().replace("_", "-")).strip()
        # Exact match (including collapsing dashes to spaces)
        if norm in self._synonym_to_canonical:
            return self._synonym_to_canonical[norm]
        norm_space = norm.replace("-", " ")
        if norm_space in self._synonym_to_canonical:
            return self._synonym_to_canonical[norm_space]
        norm_dash = norm.replace(" ", "-")
        if norm_dash in self._synonym_to_canonical:
            return self._synonym_to_canonical[norm_dash]
        # Word-boundary containment
        for key, canonical in self._synonym_to_canonical.items():
            pat = r"\b" + re.escape(key) + r"\b"
            if re.search(pat, norm) or re.search(pat, norm_space):
                return canonical
        return None

    def is_blocking(self, canonical: str) -> bool:
        return canonical in self._blocking

    def canonicals(self) -> list[str]:
        return [k for k in self.raw.keys() if not k.startswith("_")]


@dataclass
class AttributeOntology:
    """Finite attribute value sets (form, grade, hydration, salt, source, chirality)."""
    raw: dict
    _axis_tokens: dict[str, set[str]] = field(default_factory=dict)
    _axis_value_set: dict[str, set[str]] = field(default_factory=dict)
    blocking_axes: list[str] = field(default_factory=list)

    def __post_init__(self):
        for axis, spec in self.raw.items():
            if axis.startswith("_"):
                continue
            self._axis_tokens[axis] = set(spec.get("tokens", []))
            self._axis_value_set[axis] = set(spec.get("values", []))
        self.blocking_axes = list(self.raw.get("_blocking_axes", []))

    def axes(self) -> list[str]:
        return [k for k in self.raw.keys() if not k.startswith("_")]

    def validate(self, axis: str, value: str) -> str | None:
        """Return value if it's in the axis's value set (lowercased), else None."""
        if not value:
            return None
        v = value.lower().strip()
        if v in self._axis_value_set.get(axis, set()):
            return v
        return None

    def extract_from_tokens(self, tokens: set[str]) -> dict[str, str]:
        """
        Given a token set (e.g. from an ingredient-name split), return {axis: value}
        for axes where at least one token matches. If an axis has multiple matches,
        pick the longest token (most specific).
        """
        out: dict[str, str] = {}
        for axis, axis_tokens in self._axis_tokens.items():
            matches: list[str] = []
            for tok in tokens:
                if tok in axis_tokens:
                    matches.append(tok)
                    continue
                # Substring match for multi-part tokens (e.g. "d-alpha" in "d-alpha-tocopheryl")
                for at in axis_tokens:
                    if at in tok and len(at) >= 3:
                        matches.append(at)
                        break
            if matches:
                best = max(matches, key=len)
                canonical = self._canonicalize_axis_value(axis, best)
                if canonical:
                    out[axis] = canonical
        return out

    def _canonicalize_axis_value(self, axis: str, raw: str) -> str | None:
        """Map a matched token to one of the axis's value-set entries."""
        r = raw.lower().rstrip("-").strip()
        values = self._axis_value_set.get(axis, set())
        if r in values:
            return r
        # Common mappings
        if axis == "vit_d_form":
            if r in {"ergocalciferol", "vitamin-d2", "d2"}:
                return "d2"
            if r in {"cholecalciferol", "vitamin-d3", "d3"}:
                return "d3"
        if axis == "chirality":
            if r.startswith("l") and ("l-" == r or r in {"l-alpha"}):
                return "l"
            if r.startswith("d") and ("d-" == r or r in {"d-alpha"}):
                return "d"
            if r.startswith("dl"):
                return "dl"
        if axis == "salt_or_ester":
            if r in {"mononitrate"}:
                return "nitrate"
            if r in {"hcl"}:
                return "hydrochloride"
        if axis == "grade":
            if r in {"food-grade"}:
                return "food"
            if r in {"pharmaceutical"}:
                return "pharma"
        if axis == "source":
            if r in {"vegetable", "plant", "vegan"}:
                return "plant"
            if r in {"bovine", "porcine", "fish", "animal", "marine"}:
                return "animal" if r != "marine" else "marine"
            if r in {"mineral"}:
                return "mineral"
        # Fallback: if the value set has an entry that the raw starts/contains
        for v in values:
            if v in r or r in v:
                return v
        return None


@dataclass
class Ontologies:
    substances: SubstanceOntology
    certifications: CertificationOntology
    attributes: AttributeOntology


# ──────────────────────────────────────────────
# Loader (cached)
# ──────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def get_ontologies() -> Ontologies:
    substances = SubstanceOntology(_load_json(ONTOLOGY_DIR / "substances.json"))
    certifications = CertificationOntology(_load_json(ONTOLOGY_DIR / "certifications.json"))
    attributes = AttributeOntology(_load_json(ONTOLOGY_DIR / "attributes.json"))
    return Ontologies(
        substances=substances,
        certifications=certifications,
        attributes=attributes,
    )


def get_substance_ontology() -> SubstanceOntology:
    return get_ontologies().substances


def get_certification_ontology() -> CertificationOntology:
    return get_ontologies().certifications


def get_attribute_ontology() -> AttributeOntology:
    return get_ontologies().attributes
