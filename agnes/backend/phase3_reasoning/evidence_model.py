"""
Unified signal/evidence model for Phase 3 uncertainty-aware analytics.

Every metric emitted at the Phase 3 boundary carries:
    value               the number
    confidence          0–1, how sure we are
    coverage            0–1, fraction of expected signals we actually have
    source_distribution {ontology, deterministic, llm, embedding}

Source weights (fixed constants):
    ontology:           1.0
    deterministic:      0.9  (synonym / regex / exact match)
    llm:                0.6  (mid of 0.5–0.8 range)
    embedding/fuzzy:    0.4  (mid of 0.2–0.6 range)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class SourceType(Enum):
    ONTOLOGY = "ontology"
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    EMBEDDING = "embedding"


SOURCE_WEIGHTS: Dict[SourceType, float] = {
    SourceType.ONTOLOGY: 1.0,
    SourceType.DETERMINISTIC: 0.9,
    SourceType.LLM: 0.6,
    SourceType.EMBEDDING: 0.4,
}

# Map evidence.py SourceType strings → our 4-bucket SourceType
DB_SOURCE_MAP: Dict[str, SourceType] = {
    "ontology": SourceType.ONTOLOGY,
    "sku-regex": SourceType.DETERMINISTIC,
    "rule": SourceType.DETERMINISTIC,
    "llm-inference": SourceType.LLM,
    "llm-group-inference": SourceType.LLM,
    "scrape": SourceType.EMBEDDING,
    "mock": SourceType.EMBEDDING,
}


@dataclass
class Signal:
    value: float           # 0–1 normalized
    confidence: float      # 0–1
    source_type: SourceType
    importance: float      # 0–1 (how important this attribute is)
    label: str             # e.g. "Organic", "non-GMO", "Savings Potential"


@dataclass
class AggregatedMetric:
    value: float
    confidence: float
    coverage: float
    source_distribution: Dict[str, float]
    drivers: List[Signal] = field(default_factory=list)
    weak_signals: List[Signal] = field(default_factory=list)
    uncertainty_sources: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        def _sig(s: Signal) -> dict:
            return {
                "label": s.label,
                "value": s.value,
                "confidence": s.confidence,
                "source_type": s.source_type.value,
                "importance": s.importance,
            }
        return {
            "value": self.value,
            "confidence": self.confidence,
            "coverage": self.coverage,
            "source_distribution": self.source_distribution,
            "drivers": [_sig(s) for s in self.drivers],
            "weak_signals": [_sig(s) for s in self.weak_signals],
            "uncertainty_sources": self.uncertainty_sources,
        }


def aggregate(signals: List[Signal], expected_count: int) -> AggregatedMetric:
    """
    Aggregate signals into a single uncertainty-aware metric.

    value    = Σ(v × conf × weight × imp) / Σ(conf × weight × imp)
    coverage = len(signals) / expected_count
    confidence = mean(signal.confidence × source_weight)
    """
    if not signals:
        return AggregatedMetric(
            value=0.0,
            confidence=0.0,
            coverage=0.0,
            source_distribution={st.value: 0.0 for st in SourceType},
            uncertainty_sources=["No signals available"],
        )

    weights = SOURCE_WEIGHTS
    numerator = sum(
        s.value * s.confidence * weights[s.source_type] * s.importance
        for s in signals
    )
    denominator = sum(
        s.confidence * weights[s.source_type] * s.importance
        for s in signals
    )
    value = round(numerator / denominator, 4) if denominator > 0 else 0.0
    coverage = round(len(signals) / max(expected_count, 1), 4)
    confidence = round(
        sum(s.confidence * weights[s.source_type] for s in signals) / len(signals), 4
    )

    type_weights_sum: Dict[str, float] = {st.value: 0.0 for st in SourceType}
    for s in signals:
        type_weights_sum[s.source_type.value] += weights[s.source_type]
    total_w = sum(type_weights_sum.values()) or 1.0
    source_distribution = {k: round(v / total_w, 4) for k, v in type_weights_sum.items()}

    scored = sorted(
        signals,
        key=lambda s: s.value * s.confidence * weights[s.source_type],
        reverse=True,
    )
    drivers = scored[:3]
    weak_signals = [s for s in signals if s.confidence < 0.5 and s.importance > 0.6]

    uncertainty_sources: List[str] = []
    if coverage < 0.5:
        uncertainty_sources.append(f"Low coverage ({coverage:.0%} of expected signals)")
    if any(s.source_type == SourceType.LLM for s in signals):
        uncertainty_sources.append("Some signals from LLM inference (moderate reliability)")
    if any(s.source_type == SourceType.EMBEDDING for s in signals):
        uncertainty_sources.append("Some signals from fuzzy/embedding match (lower reliability)")
    if confidence < 0.4:
        uncertainty_sources.append("Overall confidence low — treat recommendation with caution")

    return AggregatedMetric(
        value=value,
        confidence=confidence,
        coverage=coverage,
        source_distribution=source_distribution,
        drivers=drivers,
        weak_signals=weak_signals,
        uncertainty_sources=uncertainty_sources,
    )
