"""
Unit tests for the enhanced Agnes pipeline modules.

Tests:
  - Ontology loader (substances, certifications, attributes)
  - Attribute extractor (deterministic tiers)
  - Constraint-aware clustering (substance clusters, links)
  - Structured extractor (HTML cleaning)
  - Contradiction detector (rule checks)

Run:
    cd agnes/
    python -m pytest tests/test_enhanced.py -v
    # or: python tests/test_enhanced.py
"""

import sys
import json
sys.path.insert(0, ".")


# ──────────────────────────────────────────────
# Ontology Tests
# ──────────────────────────────────────────────

def test_substance_ontology():
    """Test substance canonicalization and alias matching."""
    from backend.ontology import get_substance_ontology

    subs = get_substance_ontology()

    # Exact canonical match
    assert subs.canonicalize("citric-acid") == "citric-acid"

    # Alias match
    assert subs.canonicalize("e330") == "citric-acid"
    assert subs.canonicalize("vitamin-c") == "ascorbic-acid"  # merge_with
    assert subs.canonicalize("cholecalciferol") == "vitamin-d3"

    # Case insensitive
    assert subs.canonicalize("Citric-Acid") == "citric-acid"

    # Unknown returns None
    assert subs.canonicalize("unobtanium") is None
    assert subs.canonicalize("") is None

    # Category lookup
    assert subs.category_of("citric-acid") == "acidulant"
    assert subs.category_of("ascorbic-acid") == "vitamin"

    # Canonicals list
    canonicals = subs.canonicals()
    assert len(canonicals) > 100
    assert "citric-acid" in canonicals

    print("  ✓ Substance ontology: all checks passed")
    return True


def test_certification_ontology():
    """Test certification canonicalization with synonym matching."""
    from backend.ontology import get_certification_ontology

    certs = get_certification_ontology()

    # Exact match
    assert certs.canonicalize("organic") == "organic"
    assert certs.canonicalize("non-gmo") == "non-gmo"

    # Synonym match
    assert certs.canonicalize("USDA Organic") == "organic"
    assert certs.canonicalize("GMP Quality Assured") == "gmp"
    assert certs.canonicalize("Non-GMO Project Verified") == "non-gmo"

    # Blocking check
    assert certs.is_blocking("organic") is True
    assert certs.is_blocking("gmp") is False

    # Unknown
    assert certs.canonicalize("made-up-cert") is None

    print("  ✓ Certification ontology: all checks passed")
    return True


def test_attribute_ontology():
    """Test attribute axis matching from tokens."""
    from backend.ontology import get_attribute_ontology

    attrs = get_attribute_ontology()

    # Axes list
    axes = attrs.axes()
    assert "form" in axes
    assert "hydration" in axes
    assert "vit_d_form" in axes

    # Validate
    assert attrs.validate("form", "powder") == "powder"
    assert attrs.validate("form", "invalid") is None
    assert attrs.validate("hydration", "anhydrous") == "anhydrous"

    # Token extraction
    tokens = {"vitamin", "d3", "cholecalciferol"}
    result = attrs.extract_from_tokens(tokens)
    assert result.get("vit_d_form") == "d3"

    tokens2 = {"citric", "acid", "anhydrous"}
    result2 = attrs.extract_from_tokens(tokens2)
    assert result2.get("hydration") == "anhydrous"

    # Blocking axes
    assert "hydration" in attrs.blocking_axes
    assert "salt_or_ester" in attrs.blocking_axes

    print("  ✓ Attribute ontology: all checks passed")
    return True


# ──────────────────────────────────────────────
# Attribute Extractor Tests
# ──────────────────────────────────────────────

def test_deterministic_extraction():
    """Test tiers 1-3 of attribute extraction (no LLM)."""
    from backend.phase1_extraction.attribute_extractor import CardDraft, _apply_deterministic_tiers
    from backend.ontology import get_ontologies

    onts = get_ontologies()

    # Test vitamin D3 cholecalciferol
    draft = CardDraft(product_id=1, raw_ingredient_name="vitamin-d3-cholecalciferol")
    _apply_deterministic_tiers(draft, onts)
    assert draft.substance == "vitamin-d3", f"Expected vitamin-d3, got {draft.substance}"
    assert draft.vit_d_form == "d3", f"Expected d3, got {draft.vit_d_form}"

    # Test citric acid
    draft2 = CardDraft(product_id=2, raw_ingredient_name="citric-acid")
    _apply_deterministic_tiers(draft2, onts)
    assert draft2.substance == "citric-acid"

    # Test with alias
    draft3 = CardDraft(product_id=3, raw_ingredient_name="e330")
    _apply_deterministic_tiers(draft3, onts)
    assert draft3.substance == "citric-acid"

    # Test anhydrous detection
    draft4 = CardDraft(product_id=4, raw_ingredient_name="citric-acid-anhydrous")
    _apply_deterministic_tiers(draft4, onts)
    assert draft4.hydration == "anhydrous", f"Expected anhydrous, got {draft4.hydration}"

    print("  ✓ Deterministic extraction: all checks passed")
    return True


def test_card_draft_set_field():
    """Test that set_field respects priority (doesn't overwrite)."""
    from backend.phase1_extraction.attribute_extractor import CardDraft

    draft = CardDraft(product_id=1, raw_ingredient_name="test")

    # First set should work
    draft.set_field("substance", "citric-acid", "ontology", "test", 1.0)
    assert draft.substance == "citric-acid"

    # Second set should NOT overwrite
    draft.set_field("substance", "malic-acid", "llm", "test", 0.5)
    assert draft.substance == "citric-acid"  # Still the first value

    # None should be ignored
    draft2 = CardDraft(product_id=2, raw_ingredient_name="test")
    draft2.set_field("substance", None, "ontology", "test", 1.0)
    assert draft2.substance is None

    print("  ✓ CardDraft.set_field: all checks passed")
    return True


# ──────────────────────────────────────────────
# Clustering Tests
# ──────────────────────────────────────────────

def test_substance_clustering():
    """Test hard grouping by substance."""
    from backend.phase1_extraction.semantic_matcher import cluster_by_substance

    # Mock cards
    cards = [
        {"ProductId": 1, "Substance": "citric-acid", "Form": "powder", "RawIngredientName": "citric-acid",
         "Grade": None, "Hydration": "anhydrous", "SaltOrEster": None, "Source": None,
         "SourceDetail": None, "Chirality": None, "VitDForm": None, "VitB12Form": None, "TocopherolForm": None},
        {"ProductId": 2, "Substance": "citric-acid", "Form": "powder", "RawIngredientName": "non-gmo-citric-acid",
         "Grade": None, "Hydration": "anhydrous", "SaltOrEster": None, "Source": None,
         "SourceDetail": None, "Chirality": None, "VitDForm": None, "VitB12Form": None, "TocopherolForm": None},
        {"ProductId": 3, "Substance": "citric-acid", "Form": "liquid", "RawIngredientName": "citric-acid-liquid",
         "Grade": None, "Hydration": None, "SaltOrEster": None, "Source": None,
         "SourceDetail": None, "Chirality": None, "VitDForm": None, "VitB12Form": None, "TocopherolForm": None},
        {"ProductId": 4, "Substance": "malic-acid", "Form": "powder", "RawIngredientName": "malic-acid",
         "Grade": None, "Hydration": None, "SaltOrEster": None, "Source": None,
         "SourceDetail": None, "Chirality": None, "VitDForm": None, "VitB12Form": None, "TocopherolForm": None},
    ]

    clusters = cluster_by_substance(cards)
    assert len(clusters) == 2, f"Expected 2 clusters, got {len(clusters)}"

    # Find citric acid cluster
    citric_cluster = next(c for c in clusters if c.substance == "citric-acid")
    assert len(citric_cluster.product_ids) == 3
    assert citric_cluster.unified_attrs.get("hydration") is None or "anhydrous" in str(citric_cluster.unified_attrs) or "hydration" in citric_cluster.divergent_attrs
    assert "form" in citric_cluster.divergent_attrs  # powder vs liquid

    print("  ✓ Substance clustering: all checks passed")
    return True


# ──────────────────────────────────────────────
# Structured Extractor Tests
# ──────────────────────────────────────────────

def test_html_cleaning():
    """Test HTML tag stripping and whitespace normalization."""
    from backend.phase2_enrichment.structured_extractor import clean_html

    html = "<div><p>Hello  <b>World</b></p>  <br/>Foo</div>"
    cleaned = clean_html(html)
    assert "<" not in cleaned
    assert "Hello" in cleaned
    assert "World" in cleaned

    # Truncation
    long_html = "x" * 20000
    cleaned_long = clean_html(long_html, max_chars=100)
    assert len(cleaned_long) <= 100

    print("  ✓ HTML cleaning: all checks passed")
    return True


# ──────────────────────────────────────────────
# Contradiction Detector Tests
# ──────────────────────────────────────────────

def test_vegan_animal_conflict_detection():
    """Test vegan-animal contradiction rule."""
    from backend.phase2_enrichment.contradiction_detector import _check_vegan_animal_conflict

    cards = [
        {
            "ProductId": 100,
            "Substance": "gelatin",
            "Source": "animal",
            "Certifications": ["vegan"],
            "Form": None, "Grade": None,
        },
        {
            "ProductId": 101,
            "Substance": "pea-protein",
            "Source": "plant",
            "Certifications": ["vegan"],
            "Form": None, "Grade": None,
        },
    ]

    contradictions = _check_vegan_animal_conflict(cards)
    # Product 100 should flag, 101 should not
    assert len(contradictions) >= 1
    flagged_ids = [json.loads(c["DetailJson"])["product_id"] for c in contradictions]
    assert 100 in flagged_ids
    assert 101 not in flagged_ids

    print("  ✓ Vegan-animal conflict detection: all checks passed")
    return True


# ──────────────────────────────────────────────
# SKU Parser Token Tests
# ──────────────────────────────────────────────

def test_tokens_from_ingredient():
    """Test token splitting for axis matching."""
    from backend.phase1_extraction.sku_parser import tokens_from_ingredient

    tokens = tokens_from_ingredient("vitamin-d3-cholecalciferol")
    assert "vitamin-d3-cholecalciferol" in tokens
    assert "vitamin-d3" in tokens or "d3" in tokens or "cholecalciferol" in tokens

    empty = tokens_from_ingredient("")
    assert len(empty) == 0

    print("  ✓ tokens_from_ingredient: all checks passed")
    return True


# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("ENHANCED PIPELINE UNIT TESTS")
    print("=" * 60)

    tests = [
        ("Substance Ontology", test_substance_ontology),
        ("Certification Ontology", test_certification_ontology),
        ("Attribute Ontology", test_attribute_ontology),
        ("Deterministic Extraction", test_deterministic_extraction),
        ("CardDraft.set_field", test_card_draft_set_field),
        ("Substance Clustering", test_substance_clustering),
        ("HTML Cleaning", test_html_cleaning),
        ("Vegan-Animal Conflict", test_vegan_animal_conflict_detection),
        ("tokens_from_ingredient", test_tokens_from_ingredient),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            result = test_fn()
            if result:
                passed += 1
            else:
                failed += 1
                print(f"  ✗ {name}: FAILED")
        except Exception as e:
            failed += 1
            print(f"  ✗ {name}: ERROR - {e}")

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'='*60}")
