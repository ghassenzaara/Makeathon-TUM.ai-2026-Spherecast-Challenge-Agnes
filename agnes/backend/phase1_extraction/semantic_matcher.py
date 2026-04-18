"""
Semantic Matcher — groups ingredients by functional equivalence.

Two-stage strategy:
  1. Exact name match: identical canonical names across companies
  2. Semantic similarity: OpenAI embeddings + cosine similarity for near-equivalents
     (e.g. 'sunflower-lecithin' ≈ 'soy-lecithin')

Uses Union-Find (Disjoint Set) for efficient clustering.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from backend.config import (
    OPENAI_API_KEY,
    OPENAI_EMBEDDING_MODEL,
    SIMILARITY_THRESHOLD,
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

def _get_openai_embeddings(texts: list[str]) -> np.ndarray:
    """
    Get embeddings from OpenAI API in batches.
    Returns np.ndarray of shape (len(texts), embedding_dim).
    """
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    all_embeddings = []

    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        logger.info(
            f"Embedding batch {i // EMBEDDING_BATCH_SIZE + 1}"
            f" ({len(batch)} items)..."
        )
        response = client.embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,
            input=batch,
        )
        batch_embeddings = [e.embedding for e in response.data]
        all_embeddings.extend(batch_embeddings)

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
    embeddings = _get_openai_embeddings(readable_names)

    # Cache results
    np.savez_compressed(str(_EMBEDDING_CACHE_PATH), embeddings=embeddings)
    _NAMES_CACHE_PATH.write_text(json.dumps(ingredient_names))
    logger.info("Embeddings cached.")

    return embeddings


# ──────────────────────────────────────────────
# Clustering
# ──────────────────────────────────────────────

@dataclass
class IngredientCluster:
    """A cluster of semantically similar ingredient names."""
    canonical_name: str          # Most common name in the cluster
    member_names: list[str]      # All ingredient names in the cluster
    avg_similarity: float        # Average pairwise similarity within the cluster


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
