"""
Agnes ontology layer.

Central place for canonical vocabularies shared across Phase 1 and Phase 2:
  - substances.json: canonical ingredient names + aliases
  - certifications.json: canonical cert names + synonyms
  - attributes.json: finite value sets for structured attributes
"""

from backend.ontology.loader import (
    get_ontologies,
    get_substance_ontology,
    get_certification_ontology,
    get_attribute_ontology,
)

__all__ = [
    "get_ontologies",
    "get_substance_ontology",
    "get_certification_ontology",
    "get_attribute_ontology",
]
