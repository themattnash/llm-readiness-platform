from __future__ import annotations

from dataclasses import dataclass
from typing import List
import statistics


@dataclass
class ReliabilityMetrics:
    # Aggregated reliability metrics for a single eval run
    # All metrics are normalized to [0.0, 1.0]
    hallucination_accuracy: float
    refusal_accuracy: float
    safety_accuracy: float


def compute_hallucination_accuracy(rows: List[dict]) -> float:
    # Hallucination index = 1 - average hallucination score
    scores = [float(r["score"]) for r in rows if r.get("category") == "hallucination"]
    if not scores:
        return 0.0
    return 1.0 - statistics.mean(scores)


def compute_refusal_accuracy(rows: List[dict]) -> float:
    scores = [float(r["score"]) for r in rows if r.get("category") == "refusal"]
    if not scores:
        return 1.0
    return statistics.mean(scores)


def compute_safety_accuracy(rows: List[dict]) -> float:
    scores = [float(r["score"]) for r in rows if r.get("category") == "safety"]
    if not scores:
        return 1.0
    return statistics.mean(scores)


def compute_reliability_metrics(rows: List[dict]) -> ReliabilityMetrics:
    return ReliabilityMetrics(
        hallucination_accuracy=compute_hallucination_accuracy(rows),
        refusal_accuracy=compute_refusal_accuracy(rows),
        safety_accuracy=compute_safety_accuracy(rows),
    )
