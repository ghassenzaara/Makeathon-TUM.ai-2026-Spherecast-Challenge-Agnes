"""
Semantic Matcher — constraint-aware ingredient clustering.

Two-level grouping:
  1. **Hard groups** (exact substance match):
     All IngredientCards with the same canonical `Substance` value belong to
     one SubstitutionGroup. Members may differ on non-blocking attributes
     (form, grade, source) — those are recorded as "divergent".

  2. **Soft links** (substitution links):
     Groups whose substances are semantically related but differ on a
     *blocking* axis (hydration, salt/ester, chirality, vit-form) are
     linked as "could substitute, with caveats".  We use OpenAI embeddings
     + cosine similarity for this, but the link is annotated with the
     blocking-axis delta so Phase 3 can decide if it is acceptable.

Public API:
    cluster_by_substance(cards) -> list[SubstanceCluster]
    link_substitution_groups(clusters, embeddings) -> list[SubstitutionLink]
    cluster_ingredients_exact_only(names)  -- backward-compat fallback
"""

import json
import logging
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from backend.config import (
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_MODEL,
    SIMILARITY_THRESHOLD,
    LINK_SIMILARITY_THRESHOLD,
    EMBEDDING_BATCH_SIZE,
    DATA_DIR,
)

logger = logging.getLogger(__name__)

# Path to cache embeddings so we don't re-call OpenAI on reruns
_EMBEDDING_CACHE_PATH = DATA_DIR / "ingredient_embeddings.npz"
_NAMES_CACHE_PATH = DATA_DIR / "ingredient_names.json"


# ──────────────────────────────────────────────
# Union-Find data structure
# ──────────────────────────────────────────────

class UnionFind:
    """Weighted union-find with path compression for ingredient clustering."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def groups(self) -> dict[int, list[int]]:
        """Return {root_index: [member_indices]}."""
        result: dict[int, list[int]] = {}
        for i in range(len(self.parent)):
            root = self.find(i)
            result.setdefault(root, []).append(i)
        return result


# ──────────────────────────────────────────────
# Embedding generation
# ──────────────────────────────────────────────

def _get_gemini_embeddings(texts: list[str]) -> np.ndarray:
    """
    Get embeddings from Gemini API in batches.
    Returns np.ndarray of shape (len(texts), embedding_dim).
    """
    from google import genai as _genai

    client = _genai.Client(api_key=GEMINI_API_KEY)
    all_embeddings = []

    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        logger.info(
            f"Embedding batch {i // EMBEDDING_BATCH_SIZE + 1}"
            f" ({len(batch)} items)..."
        )
        resp = client.models.embed_content(
            model=GEMINI_EMBEDDING_MODEL,
            contents=batch,
        )
        all_embeddings.extend([list(e.values) for e in resp.embeddings])

    return np.array(all_embeddings)


def build_ingredient_embeddings(
    ingredient_names: list[str],
    force_refresh: bool = False,
) -> np.ndarray:
    """
    Build or load cached embeddings for a list of ingredient names.

    Args:
        ingredient_names: List of unique, normalized ingredient names.
        force_refresh: If True, re-fetch from OpenAI even if cache exists.

    Returns:
        np.ndarray of shape (len(ingredient_names), embedding_dim)
    """
    # Check cache
    if (
        not force_refresh
        and _EMBEDDING_CACHE_PATH.exists()
        and _NAMES_CACHE_PATH.exists()
    ):
        cached_names = json.loads(_NAMES_CACHE_PATH.read_text())
        if cached_names == ingredient_names:
            logger.info("Loading cached embeddings...")
            data = np.load(str(_EMBEDDING_CACHE_PATH))
            return data["embeddings"]

    # Generate new embeddings
    # Prepare human-readable versions for better embedding quality
    readable_names = [
        name.replace("-", " ") for name in ingredient_names
    ]

    logger.info(f"Generating embeddings for {len(readable_names)} ingredients...")
    embeddings = _get_gemini_embeddings(readable_names)

    # Cache results
    np.savez_compressed(str(_EMBEDDING_CACHE_PATH), embeddings=embeddings)
    _NAMES_CACHE_PATH.write_text(json.dumps(ingredient_names))
    logger.info("Embeddings cached.")

    return embeddings


# ──────────────────────────────────────────────
# Constraint-aware clustering data models
# ──────────────────────────────────────────────

@dataclass
class IngredientCluster:
    """A cluster of semantically similar ingredient names (backward compat)."""
    canonical_name: str          # Most common name in the cluster
    member_names: list[str]      # All ingredient names in the cluster
    avg_similarity: float        # Average pairwise similarity within the cluster


@dataclass
class SubstanceCluster:
    """
    A hard group: all members share the same canonical Substance.
    Non-blocking attribute differences are recorded as divergent.
    """
    substance: str
    product_ids: list[int] = field(default_factory=list)
    raw_names: list[str] = field(default_factory=list)
    # Unified attributes: values all members agree on
    unified_attrs: dict[str, str] = field(default_factory=dict)
    # Divergent attributes: {axis: {value: [product_ids with that value]}}
    divergent_attrs: dict[str, dict[str, list[int]]] = field(default_factory=dict)


@dataclass
class SubstitutionLink:
    """A soft link between two SubstanceCluster groups."""
    from_substance: str
    to_substance: str
    similarity: float
    caveats: list[str] = field(default_factory=list)  # blocking-axis deltas


# ──────────────────────────────────────────────
# Hard grouping: cluster by canonical substance
# ──────────────────────────────────────────────

_ATTRIBUTE_AXES = [
    "form", "grade", "hydration", "salt_or_ester",
    "source", "source_detail", "chirality",
    "vit_d_form", "vit_b12_form", "tocopherol_form",
]

_DB_COLUMN_FOR_AXIS = {
    "form": "Form",
    "grade": "Grade",
    "hydration": "Hydration",
    "salt_or_ester": "SaltOrEster",
    "source": "Source",
    "source_detail": "SourceDetail",
    "chirality": "Chirality",
    "vit_d_form": "VitDForm",
    "vit_b12_form": "VitB12Form",
    "tocopherol_form": "TocopherolForm",
}


def cluster_by_substance(cards: list[dict]) -> list[SubstanceCluster]:
    """
    Group IngredientCard rows by their canonical Substance.
    Compute unified and divergent attributes per group.

    Args:
        cards: list of dicts from `get_all_ingredient_cards()`.

    Returns:
        list of SubstanceCluster, sorted by number of members (desc).
    """
    subs_map: dict[str, list[dict]] = defaultdict(list)
    for card in cards:
        sub = card.get("Substance")
        if not sub:
            sub = card.get("RawIngredientName", "unknown")
        subs_map[sub].append(card)

    clusters: list[SubstanceCluster] = []
    for substance, members in subs_map.items():
        cluster = SubstanceCluster(
            substance=substance,
            product_ids=[m["ProductId"] for m in members],
            raw_names=list({m.get("RawIngredientName", "") for m in members}),
        )

        # Compute unified vs divergent attributes.
        for axis in _ATTRIBUTE_AXES:
            col = _DB_COLUMN_FOR_AXIS[axis]
            value_groups: dict[str, list[int]] = defaultdict(list)
            for m in members:
                v = m.get(col) or None
                if v:
                    value_groups[v].append(m["ProductId"])

            if len(value_groups) == 0:
                # No data for this axis → skip
                pass
            elif len(value_groups) == 1:
                # All members agree
                cluster.unified_attrs[axis] = list(value_groups.keys())[0]
            else:
                # Divergent
                cluster.divergent_attrs[axis] = dict(value_groups)

        clusters.append(cluster)

    clusters.sort(key=lambda c: len(c.product_ids), reverse=True)
    logger.info(
        "Substance clustering: %d clusters from %d cards",
        len(clusters), len(cards),
    )
    return clusters


# ──────────────────────────────────────────────
# Soft linking: substitution links across groups
# ──────────────────────────────────────────────

def link_substitution_groups(
    clusters: list[SubstanceCluster],
    threshold: float | None = None,
    force_refresh_embeddings: bool = False,
) -> list[SubstitutionLink]:
    """
    Build cross-group substitution links using embedding similarity.

    Only links groups whose substances are ≥ threshold similar (default
    LINK_SIMILARITY_THRESHOLD from config). For each link, record caveats
    for any blocking-axis difference.

    Args:
        clusters: output of cluster_by_substance()
        threshold: similarity cutoff (default from config)
        force_refresh_embeddings: re-call OpenAI

    Returns:
        list of SubstitutionLink
    """
    if threshold is None:
        threshold = LINK_SIMILARITY_THRESHOLD

    if len(clusters) < 2:
        return []

    substances = [c.substance for c in clusters]
    sub_to_idx = {s: i for i, s in enumerate(substances)}

    # Get or build embeddings
    if not GEMINI_API_KEY:
        logger.warning("No GEMINI_API_KEY — skipping substitution linking.")
        return []

    embeddings = build_ingredient_embeddings(
        substances, force_refresh=force_refresh_embeddings,
    )

    n = len(substances)
    logger.info(f"Computing {n}x{n} cosine similarity for substitution linking...")
    sim_matrix = cosine_similarity(embeddings)

    from backend.ontology import get_ontologies
    onts = get_ontologies()
    blocking_axes = set(onts.attributes.blocking_axes)

    links: list[SubstitutionLink] = []
    for i in range(n):
        for j in range(i + 1, n):
            sim = float(sim_matrix[i, j])
            if sim < threshold:
                continue
            # Skip if they'd already be in the same hard group
            if substances[i] == substances[j]:
                continue

            # Compute caveats: blocking-axis differences
            caveats: list[str] = []
            ci, cj = clusters[i], clusters[j]
            for axis in blocking_axes:
                vi = ci.unified_attrs.get(axis)
                vj = cj.unified_attrs.get(axis)
                if vi and vj and vi != vj:
                    caveats.append(
                        f"{axis}: {ci.substance}={vi} vs {cj.substance}={vj}"
                    )

            links.append(SubstitutionLink(
                from_substance=substances[i],
                to_substance=substances[j],
                similarity=round(sim, 4),
                caveats=caveats,
            ))

    links.sort(key=lambda l: l.similarity, reverse=True)
    logger.info(
        "Substitution linking: %d links above threshold=%.2f "
        "(%d with blocking caveats)",
        len(links), threshold,
        sum(1 for l in links if l.caveats),
    )
    return links


# ──────────────────────────────────────────────
# Legacy API (backward compatibility with existing callers)
# ──────────────────────────────────────────────

def cluster_ingredients(
    names: list[str],
    embeddings: np.ndarray,
    threshold: float = None,
) -> list[IngredientCluster]:
    """
    Group ingredient names by cosine similarity using Union-Find.

    Args:
        names: List of unique ingredient names.
        embeddings: Corresponding embeddings matrix.
        threshold: Minimum cosine similarity to merge (default from config).

    Returns:
        List of IngredientCluster objects.
    """
    if threshold is None:
        threshold = SIMILARITY_THRESHOLD

    n = len(names)
    logger.info(f"Computing {n}x{n} cosine similarity matrix...")
    sim_matrix = cosine_similarity(embeddings)

    # Union-Find clustering
    uf = UnionFind(n)
    merge_count = 0

    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i, j] >= threshold:
                uf.union(i, j)
                merge_count += 1

    logger.info(f"Performed {merge_count} merges at threshold={threshold}")

    # Build clusters
    groups = uf.groups()
    clusters = []

    for root, member_indices in groups.items():
        member_names = [names[idx] for idx in member_indices]

        # Compute average pairwise similarity within cluster
        if len(member_indices) > 1:
            sub_sims = []
            for ii in range(len(member_indices)):
                for jj in range(ii + 1, len(member_indices)):
                    sub_sims.append(
                        sim_matrix[member_indices[ii], member_indices[jj]]
                    )
            avg_sim = float(np.mean(sub_sims))
        else:
            avg_sim = 1.0

        # Choose canonical name: the most common or shortest
        canonical = min(member_names, key=len)

        clusters.append(IngredientCluster(
            canonical_name=canonical,
            member_names=sorted(member_names),
            avg_similarity=round(avg_sim, 4),
        ))

    # Sort clusters by size (largest first)
    clusters.sort(key=lambda c: len(c.member_names), reverse=True)

    logger.info(
        f"Formed {len(clusters)} clusters from {n} unique names "
        f"(threshold={threshold})"
    )
    return clusters


def cluster_ingredients_exact_only(
    names: list[str],
) -> list[IngredientCluster]:
    """
    Fallback clustering using exact name matching only (no embeddings).
    Useful when OpenAI API key is not available.
    """
    # Each unique name is its own cluster
    clusters = []
    for name in sorted(set(names)):
        clusters.append(IngredientCluster(
            canonical_name=name,
            member_names=[name],
            avg_similarity=1.0,
        ))

    clusters.sort(key=lambda c: c.canonical_name)
    logger.info(
        f"Exact-match clustering: {len(clusters)} clusters from {len(names)} names"
    )
    return clusters
